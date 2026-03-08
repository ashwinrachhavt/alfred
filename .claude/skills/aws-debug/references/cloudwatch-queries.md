# CloudWatch Logs Query Reference

## Log Insights Queries

Use these with CloudWatch Logs Insights console or CLI.

### Basic Queries

**Recent Errors:**
```
fields @timestamp, @message
| filter @message like /ERROR|Exception|error/
| sort @timestamp desc
| limit 50
```

**Request Latency:**
```
fields @timestamp, @message
| filter @message like /Completed/
| parse @message "Completed * in *ms" as status, duration
| stats avg(duration), max(duration), min(duration) by bin(5m)
```

**HTTP Status Codes:**
```
fields @timestamp, @message
| filter @message like /Completed/
| parse @message "Completed * " as status
| stats count(*) by status
```

### Rails-Specific Queries

**ActiveRecord Queries:**
```
fields @timestamp, @message
| filter @message like /ActiveRecord/
| sort @timestamp desc
| limit 100
```

**Slow Queries (>100ms):**
```
fields @timestamp, @message
| filter @message like /Load/
| parse @message "* Load (*ms)" as model, duration
| filter duration > 100
| sort duration desc
| limit 50
```

**Controller Actions:**
```
fields @timestamp, @message
| filter @message like /Processing by/
| parse @message "Processing by *#* as" as controller, action
| stats count(*) by controller, action
| sort count desc
```

**Failed Requests:**
```
fields @timestamp, @message
| filter @message like /Completed 5/ or @message like /Completed 4/
| sort @timestamp desc
| limit 50
```

### Background Job Queries

**Solid Queue Errors:**
```
fields @timestamp, @message
| filter @message like /ERROR|Failed|Exception/
| sort @timestamp desc
| limit 50
```

**Job Execution Times:**
```
fields @timestamp, @message
| filter @message like /Performed/
| parse @message "Performed * in *ms" as job, duration
| stats avg(duration), count(*) by job
```

### Memory & Performance

**Memory Usage:**
```
fields @timestamp, @message
| filter @message like /memory|Memory|RSS|heap/
| sort @timestamp desc
| limit 100
```

**Container Restarts:**
```
fields @timestamp, @message
| filter @message like /Starting|Stopping|Terminated/
| sort @timestamp desc
| limit 50
```

---

## CLI Log Commands

### Filter Patterns

**Error Patterns:**
```bash
aws logs filter-log-events \
  --log-group-name /ecs/pr-${PR_NUMBER}/rails-app \
  --filter-pattern "ERROR" \
  --start-time $(date -v-1H +%s000)
```

**Exception Stack Traces:**
```bash
aws logs filter-log-events \
  --log-group-name /ecs/pr-${PR_NUMBER}/rails-app \
  --filter-pattern "?Exception ?Error ?Traceback" \
  --start-time $(date -v-1H +%s000)
```

**Specific Model Errors:**
```bash
aws logs filter-log-events \
  --log-group-name /ecs/pr-${PR_NUMBER}/rails-app \
  --filter-pattern "Deal ActiveRecord" \
  --start-time $(date -v-30M +%s000)
```

**HTTP 500 Responses:**
```bash
aws logs filter-log-events \
  --log-group-name /ecs/pr-${PR_NUMBER}/rails-app \
  --filter-pattern '"Completed 500"' \
  --start-time $(date -v-1H +%s000)
```

### Time Ranges

**Last Hour:**
```bash
--start-time $(date -v-1H +%s000)
```

**Last 30 Minutes:**
```bash
--start-time $(date -v-30M +%s000)
```

**Last 24 Hours:**
```bash
--start-time $(date -v-1d +%s000)
```

**Specific Date Range:**
```bash
--start-time 1706745600000 --end-time 1706832000000
```

### Output Formats

**Just Messages:**
```bash
--query 'events[].message' --output text
```

**With Timestamps:**
```bash
--query 'events[].{time:timestamp,msg:message}' --output table
```

**JSON for Processing:**
```bash
--output json | jq '.events[].message'
```

---

## Metrics Queries

**ECS Service CPU:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ClusterName,Value=pr-${PR_NUMBER} Name=ServiceName,Value=rails-app \
  --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Average
```

**ECS Service Memory:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name MemoryUtilization \
  --dimensions Name=ClusterName,Value=pr-${PR_NUMBER} Name=ServiceName,Value=rails-app \
  --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Average Maximum
```

**ALB Request Count:**
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name RequestCount \
  --dimensions Name=TargetGroup,Value=targetgroup/pr-${PR_NUMBER}-rails/xxx \
  --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Sum
```

---

## Log Groups Reference

| Service | Log Group |
|---------|-----------|
| Rails App | `/ecs/pr-{number}/rails-app` |
| Solid Queue | `/ecs/pr-{number}/solid-queue` |
| Mailhog | `/ecs/pr-{number}/mailhog` |
| Migration | `/ecs/pr-{number}/migration` |
| AgentCore | `/ecs/pr-{number}/agentcore` |
