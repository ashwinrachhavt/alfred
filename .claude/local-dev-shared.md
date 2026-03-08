# Local Dev — Shared Infrastructure

> **Required by ALL 3 solutions.** Apply these changes FIRST, then layer on Solution A, B, or C.

These changes fix the 3 critical gaps identified in the architecture review:

1. `Agentic.enabled?` gate blocks all local execution
2. `Agentic::Response` assumes AWS SDK response shape
3. Missing `langchain-anthropic` dependency

---

## File 1: `app/app/services/agentic.rb`

**Change:** Modify `enabled?` to accept `LOCAL_AGENTIC_URL`

Replace lines 4-6:

```ruby
# BEFORE
def self.enabled?
  ENV["AGENTCORE_RUNTIME_ARN"].present?
end
```

```ruby
# AFTER
def self.enabled?
  ENV["AGENTCORE_RUNTIME_ARN"].present? || ENV["LOCAL_AGENTIC_URL"].present?
end
```

---

## File 2: `app/app/services/agentic/client.rb`

**Change:** Full rewrite — factory pattern for local vs AWS mode

```ruby
# frozen_string_literal: true

module Agentic
  class Client
    attr_reader :client

    def initialize
      if local_mode?
        require "net/http"
        require "uri"
        @base_url = ENV.fetch("LOCAL_AGENTIC_URL")
      else
        @client = Aws::BedrockAgentCore::Client.new
      end
    end

    def invoke_agent(agent:, params:, session_id:)
      if local_mode?
        invoke_local(agent: agent, params: params, session_id: session_id)
      else
        invoke_remote(agent: agent, params: params, session_id: session_id)
      end
    end

    private

    def local_mode?
      ENV["LOCAL_AGENTIC_URL"].present?
    end

    def invoke_local(agent:, params:, session_id:)
      payload = {
        input: { agent: agent, params: params, session_id: session_id },
        context: {},
      }.to_json

      uri = URI("#{@base_url}/invocations")
      http = Net::HTTP.new(uri.host, uri.port)
      http.read_timeout = 300 # agents can take minutes
      request = Net::HTTP::Post.new(uri.path, {
        "Content-Type" => "application/json",
        "Accept" => "application/json",
        "x-amzn-bedrock-agentcore-runtime-session-id" => session_id,
      })
      request.body = payload

      Rails.logger.info("Invoking agent=#{agent} locally at #{uri}")

      http_response = http.request(request)
      LocalAgentResponse.new(http_response, session_id)
    rescue StandardError => e
      Rails.logger.error("Local agent invocation failed: #{e.message}")
      Response.new(nil, error: e)
    end

    def invoke_remote(agent:, params:, session_id:)
      payload = {
        input: { agent: agent, params: params, session_id: session_id },
      }.to_json

      request_params = {
        agent_runtime_arn: ENV["AGENTCORE_RUNTIME_ARN"],
        payload: payload,
        content_type: "application/json",
        accept: "application/json",
        runtime_session_id: session_id,
      }

      Rails.logger.info("Invoking agent=#{agent} with runtime_session_id=#{session_id}")
      Response.new(client.invoke_agent_runtime(request_params))
    rescue Aws::Errors::ServiceError => e
      Response.new(nil, error: e)
    end
  end
end
```

---

## File 3: `app/app/services/agentic/local_agent_response.rb` (NEW)

**Purpose:** Adapter that quacks like the AWS SDK `InvokeAgentRuntimeResponse`.

`Agentic::Response` reads these fields from the raw response:

| Field | AWS SDK type | What we provide |
|---|---|---|
| `.status_code` | Integer | `http_response.code.to_i` |
| `.runtime_session_id` | String | Passed-through session ID |
| `.content_type` | String | `"application/json"` |
| `.mcp_session_id` | String/nil | `nil` |
| `.trace_id` | String/nil | `nil` |
| `.response.read` | String (IO) | `http_response.body` (via `ResponseBody` wrapper) |

```ruby
# frozen_string_literal: true

module Agentic
  class LocalAgentResponse
    # Inner class that mimics the streaming IO interface of AWS SDK response
    # Agentic::Response calls raw_response.response.read to get the body
    class ResponseBody
      def initialize(body)
        @body = body
        @read = false
      end

      def read
        return "" if @read

        @read = true
        @body
      end
    end

    attr_reader :status_code, :runtime_session_id, :content_type,
                :mcp_session_id, :trace_id, :response

    def initialize(http_response, session_id)
      @status_code = http_response.code.to_i
      @runtime_session_id = session_id
      @content_type = "application/json"
      @mcp_session_id = nil
      @trace_id = nil
      @response = ResponseBody.new(http_response.body)
    end
  end
end
```

---

## File 4: `agentic/lois/agents/base_agent.py`

**Change:** Conditional LLM + memory in `get_instance()` (replaces lines 31-61).

> The **Tools** section differs per solution — see each solution's file. Below shows the base version.

```python
@classmethod
async def get_instance(
    cls, allowed_tools: list[str], system_prompt: str, session_id: str
) -> Self:
    """Create a fresh agent instance with session ID.

    Supports local mode (ANTHROPIC_API_KEY or OPENAI_API_KEY set)
    and production mode (AWS Bedrock).
    """
    # --- LLM ---
    if os.environ.get("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic

        llm = ChatAnthropic(
            model="claude-sonnet-4-5-20250514",
            max_tokens=4096,
            temperature=0,
        )
    elif os.environ.get("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            max_tokens=4096,
            temperature=0,
        )
    else:
        llm = ChatBedrock(
            model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            region_name="us-west-2",
            model_kwargs={"max_tokens": 4096, "temperature": 0},
        )

    # --- Tools (Solution A/B/C each override this differently) ---
    all_tools = await get_gateway_tools(session_id=session_id)
    tools = filter_tools(all_tools, allowed_tools)
    logger.info("%s filtered to %d allowed tools", cls.__name__, len(tools))

    # --- Memory / Checkpointer ---
    memory_id = os.environ.get("AGENTCORE_MEMORY_ID", "")
    if memory_id:
        checkpointer = AgentCoreMemorySaver(memory_id, region_name="us-west-2")
    else:
        from langgraph.checkpoint.memory import MemorySaver

        checkpointer = MemorySaver()

    return cls(llm, tools, checkpointer, system=system_prompt)
```

---

## File 5: `agentic/requirements.txt`

**Change:** Add `langchain-anthropic` and optionally `langchain-openai`.

```
langchain-anthropic>=0.3.0
langchain-openai>=0.3.0      # optional — only needed if using OpenAI as LLM
```

---

## Environment Variables (shared)

### Rails `.env`

```bash
LOCAL_AGENTIC_URL=http://localhost:8080
BEDROCK_API_KEY=local-dev-key
```

### Agentic `.env`

```bash
# Set ONE of these LLM keys (Anthropic checked first, then OpenAI):
ANTHROPIC_API_KEY=sk-ant-your-key-here
# OPENAI_API_KEY=sk-your-openai-key       # alternative — use OpenAI instead
# OPENAI_MODEL=gpt-4o                      # optional — defaults to gpt-4o

RAILS_API_BASE=http://localhost:3000
BEDROCK_API_KEY=local-dev-key
```

### Unset / leave empty

```bash
AGENTCORE_RUNTIME_ARN=    # triggers local mode in Rails
AGENTCORE_MEMORY_ID=      # triggers MemorySaver fallback
```
