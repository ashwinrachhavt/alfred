---
name: aws-debug
description: AWS debugging skill for PR preview environments. Fetch logs from CloudWatch, inspect ECS tasks, debug container issues, check service health, and troubleshoot deployments. Tailored to the Loan Labs staging infrastructure (ECS Fargate, CloudWatch, ALB, Route53).
---

# AWS Debug Skill

Debug PR preview environments on AWS. Fetch logs, inspect containers, troubleshoot deployments, and diagnose issues without leaving the CLI.

## When This Skill Activates

- "Why is my PR environment not working?"
- "Show me the logs for PR-XXX"
- "What's wrong with the deployment?"
- "Check the ECS task status"
- "Debug the Rails container"
- "Is the service healthy?"

## Your Infrastructure Context

```
PR Environment: pr-{number}.staging.loanos.net
├── ECS Cluster: pr-{number}
├── Services:
│   ├── Rails App (port 3000, health: /up)
│   ├── Mailhog (port 8025)
│   └── Solid Queue (background jobs)
├── CloudWatch Logs: /ecs/pr-{number}/*
├── S3 Bucket: pr-{number}-bucket
└── AgentCore: Agent runtime on port 8080
```

## Security Principles

1. **Read-only by default** - Fetch/view operations only
2. **No credential exposure** - Never log secrets
3. **Scoped access** - Only PR-specific resources
4. **Audit trail** - Commands are logged

---

## Quick Reference Commands

### Get PR Number from Branch
```bash
PR_NUMBER=$(gh pr view --json number -q .number 2>/dev/null || echo "")
echo "Current PR: $PR_NUMBER"
```

### Set Environment
```bash
export AWS_REGION=us-west-2
export PR_NUMBER=552  # Your PR number
```

---

## Core Workflows

### Workflow 1: Check Service Health

**Quick Health Check:**
```bash
# Check if site is up
curl -s -o /dev/null -w "%{http_code}" https://www.pr-${PR_NUMBER}.staging.loanos.net/up

# Check ECS service status
aws ecs describe-services \
  --cluster pr-${PR_NUMBER} \
  --services rails-app \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Events:events[0:3]}' \
  --output table
```

**Detailed Service Info:**
```bash
# List all services in cluster
aws ecs list-services --cluster pr-${PR_NUMBER} --output table

# Get service details
aws ecs describe-services \
  --cluster pr-${PR_NUMBER} \
  --services rails-app solid-queue mailhog \
  --query 'services[].{Name:serviceName,Status:status,Running:runningCount,Desired:desiredCount}' \
  --output table
```

---

### Workflow 2: Fetch CloudWatch Logs

**Recent Rails Logs:**
```bash
aws logs tail /ecs/pr-${PR_NUMBER}/rails-app \
  --since 30m \
  --format short
```

**Follow Logs Live:**
```bash
aws logs tail /ecs/pr-${PR_NUMBER}/rails-app --follow
```

**Search for Errors:**
```bash
aws logs filter-log-events \
  --log-group-name /ecs/pr-${PR_NUMBER}/rails-app \
  --filter-pattern "ERROR" \
  --start-time $(date -v-1H +%s000) \
  --query 'events[].message' \
  --output text
```

**Search for Specific Text:**
```bash
aws logs filter-log-events \
  --log-group-name /ecs/pr-${PR_NUMBER}/rails-app \
  --filter-pattern "ActionController" \
  --start-time $(date -v-30M +%s000) \
  --query 'events[].message' \
  --output text
```

**Background Jobs (Solid Queue):**
```bash
aws logs tail /ecs/pr-${PR_NUMBER}/solid-queue --since 30m
```

**AgentCore Logs:**
```bash
aws logs tail /ecs/pr-${PR_NUMBER}/agentcore --since 30m
```

---

### Workflow 3: Inspect ECS Tasks

**List Running Tasks:**
```bash
aws ecs list-tasks \
  --cluster pr-${PR_NUMBER} \
  --query 'taskArns' \
  --output table
```

**Get Task Details:**
```bash
TASK_ARN=$(aws ecs list-tasks --cluster pr-${PR_NUMBER} --query 'taskArns[0]' --output text)

aws ecs describe-tasks \
  --cluster pr-${PR_NUMBER} \
  --tasks $TASK_ARN \
  --query 'tasks[0].{Status:lastStatus,Health:healthStatus,StoppedReason:stoppedReason,Containers:containers[].{Name:name,Status:lastStatus,ExitCode:exitCode}}' \
  --output yaml
```

**Find Failed Tasks:**
```bash
aws ecs list-tasks \
  --cluster pr-${PR_NUMBER} \
  --desired-status STOPPED \
  --query 'taskArns' \
  --output text | xargs -I {} aws ecs describe-tasks \
    --cluster pr-${PR_NUMBER} \
    --tasks {} \
    --query 'tasks[].{TaskArn:taskArn,StoppedReason:stoppedReason,StoppedAt:stoppedAt}' \
    --output table
```

**Container Exit Codes:**
```bash
aws ecs describe-tasks \
  --cluster pr-${PR_NUMBER} \
  --tasks $(aws ecs list-tasks --cluster pr-${PR_NUMBER} --desired-status STOPPED --query 'taskArns[0]' --output text) \
  --query 'tasks[0].containers[].{Name:name,ExitCode:exitCode,Reason:reason}' \
  --output table
```

---

### Workflow 4: Debug Container Issues

**Common Exit Codes:**
| Code | Meaning | Common Cause |
|------|---------|--------------|
| 0 | Success | Normal exit |
| 1 | Error | App crash, exception |
| 137 | SIGKILL | OOM killed, timeout |
| 143 | SIGTERM | Graceful shutdown |
| 255 | Unknown | Container runtime error |

**Check for OOM (Out of Memory):**
```bash
aws logs filter-log-events \
  --log-group-name /ecs/pr-${PR_NUMBER}/rails-app \
  --filter-pattern "OutOfMemory" \
  --start-time $(date -v-1H +%s000)
```

**Check Task Definition:**
```bash
aws ecs describe-task-definition \
  --task-definition pr-${PR_NUMBER}-rails-app \
  --query 'taskDefinition.containerDefinitions[0].{Memory:memory,CPU:cpu,Image:image}' \
  --output table
```

---

### Workflow 5: Check Load Balancer

**Target Health:**
```bash
# Get target group ARN
TG_ARN=$(aws elbv2 describe-target-groups \
  --names pr-${PR_NUMBER}-rails \
  --query 'TargetGroups[0].TargetGroupArn' \
  --output text 2>/dev/null)

# Check health
aws elbv2 describe-target-health \
  --target-group-arn $TG_ARN \
  --query 'TargetHealthDescriptions[].{Target:Target.Id,Health:TargetHealth.State,Reason:TargetHealth.Reason}' \
  --output table
```

**Check ALB Listener Rules:**
```bash
aws elbv2 describe-rules \
  --listener-arn <listener-arn> \
  --query 'Rules[?contains(Conditions[0].Values[0], `pr-${PR_NUMBER}`)].{Priority:Priority,Host:Conditions[0].Values[0]}' \
  --output table
```

---

### Workflow 6: DNS & Certificate Check

**Check DNS Resolution:**
```bash
dig +short www.pr-${PR_NUMBER}.staging.loanos.net
```

**Check Certificate:**
```bash
echo | openssl s_client -servername www.pr-${PR_NUMBER}.staging.loanos.net \
  -connect www.pr-${PR_NUMBER}.staging.loanos.net:443 2>/dev/null | \
  openssl x509 -noout -dates
```

**Check Route53 Records:**
```bash
aws route53 list-resource-record-sets \
  --hosted-zone-id <zone-id> \
  --query "ResourceRecordSets[?contains(Name, 'pr-${PR_NUMBER}')]" \
  --output table
```

---

### Workflow 7: Database Migration Status

**Check Migration Task:**
```bash
aws ecs list-tasks \
  --cluster pr-${PR_NUMBER} \
  --family pr-${PR_NUMBER}-migration \
  --query 'taskArns' \
  --output text
```

**Migration Logs:**
```bash
aws logs filter-log-events \
  --log-group-name /ecs/pr-${PR_NUMBER}/migration \
  --start-time $(date -v-1H +%s000) \
  --query 'events[].message' \
  --output text
```

---

### Workflow 8: S3 Bucket Check

**List Bucket Contents:**
```bash
aws s3 ls s3://pr-${PR_NUMBER}-bucket/ --recursive --human-readable
```

**Check Bucket Policy:**
```bash
aws s3api get-bucket-policy --bucket pr-${PR_NUMBER}-bucket 2>/dev/null || echo "No policy"
```

---

## Troubleshooting Runbooks

### "Site Returns 502/503"

1. **Check ECS service:**
   ```bash
   aws ecs describe-services --cluster pr-${PR_NUMBER} --services rails-app \
     --query 'services[0].{Running:runningCount,Events:events[0:3].message}'
   ```

2. **Check target health:**
   ```bash
   # See if containers are healthy
   ```

3. **Check recent logs:**
   ```bash
   aws logs tail /ecs/pr-${PR_NUMBER}/rails-app --since 10m
   ```

4. **Common causes:**
   - Container crashing on startup
   - Health check failing
   - Database connection issues

### "Deployment Stuck"

1. **Check deployment status:**
   ```bash
   aws ecs describe-services --cluster pr-${PR_NUMBER} --services rails-app \
     --query 'services[0].deployments[].{Status:status,Running:runningCount,Pending:pendingCount}'
   ```

2. **Check for task failures:**
   ```bash
   aws ecs list-tasks --cluster pr-${PR_NUMBER} --desired-status STOPPED
   ```

3. **Check events:**
   ```bash
   aws ecs describe-services --cluster pr-${PR_NUMBER} --services rails-app \
     --query 'services[0].events[0:5].message' --output text
   ```

### "Background Jobs Not Processing"

1. **Check Solid Queue service:**
   ```bash
   aws ecs describe-services --cluster pr-${PR_NUMBER} --services solid-queue
   ```

2. **Check Solid Queue logs:**
   ```bash
   aws logs tail /ecs/pr-${PR_NUMBER}/solid-queue --since 30m
   ```

3. **Look for errors:**
   ```bash
   aws logs filter-log-events \
     --log-group-name /ecs/pr-${PR_NUMBER}/solid-queue \
     --filter-pattern "ERROR" \
     --start-time $(date -v-1H +%s000)
   ```

### "Agent Not Responding"

1. **Check AgentCore service:**
   ```bash
   aws ecs describe-services --cluster pr-${PR_NUMBER} --services agentcore
   ```

2. **Check AgentCore logs:**
   ```bash
   aws logs tail /ecs/pr-${PR_NUMBER}/agentcore --since 30m
   ```

3. **Check API key in SSM:**
   ```bash
   aws ssm get-parameter --name /pr-${PR_NUMBER}/AGENTCORE_API_KEY --with-decryption \
     --query 'Parameter.Value' --output text | head -c 10
   echo "..."  # Don't expose full key
   ```

---

## Useful Aliases

Add to your shell config:

```bash
# AWS PR Environment Helpers
alias pr-logs='aws logs tail /ecs/pr-${PR_NUMBER}/rails-app --since 30m'
alias pr-logs-follow='aws logs tail /ecs/pr-${PR_NUMBER}/rails-app --follow'
alias pr-status='aws ecs describe-services --cluster pr-${PR_NUMBER} --services rails-app --query "services[0].{Status:status,Running:runningCount}"'
alias pr-health='curl -s -o /dev/null -w "%{http_code}" https://www.pr-${PR_NUMBER}.staging.loanos.net/up'
```

---

## Prerequisites

Ensure AWS CLI is configured:

```bash
# Check credentials
aws sts get-caller-identity

# Set region
export AWS_REGION=us-west-2

# Or configure profile
export AWS_PROFILE=staging
```
