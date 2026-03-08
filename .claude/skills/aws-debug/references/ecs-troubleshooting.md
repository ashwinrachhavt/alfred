# ECS Troubleshooting Reference

## Task States

| State | Description | Action |
|-------|-------------|--------|
| PROVISIONING | Resources being allocated | Wait |
| PENDING | Waiting for container agent | Check cluster capacity |
| ACTIVATING | Container starting | Check container logs |
| RUNNING | Healthy and running | OK |
| DEACTIVATING | Graceful shutdown | Wait |
| STOPPING | Being stopped | Wait |
| DEPROVISIONING | Releasing resources | Wait |
| STOPPED | Task ended | Check exit code/reason |

---

## Common ECS Failures

### 1. Task Fails to Start

**Symptoms:**
- Tasks stuck in PENDING
- Tasks immediately STOPPED

**Check:**
```bash
aws ecs describe-tasks \
  --cluster pr-${PR_NUMBER} \
  --tasks $(aws ecs list-tasks --cluster pr-${PR_NUMBER} --desired-status STOPPED --query 'taskArns[0]' --output text) \
  --query 'tasks[0].{StoppedReason:stoppedReason,Containers:containers[].reason}'
```

**Common Causes:**

| StoppedReason | Cause | Solution |
|---------------|-------|----------|
| "Essential container exited" | App crashed | Check container logs |
| "Task failed ELB health checks" | Health endpoint failing | Check /up endpoint |
| "CannotPullContainerError" | Image not found | Verify ECR image exists |
| "ResourceInitializationError" | ENI/secrets issue | Check IAM roles, VPC |
| "OutOfMemoryError" | Container OOM | Increase memory limit |

### 2. Container Image Pull Failures

**Error:** `CannotPullContainerError`

**Check:**
```bash
# Verify image exists
aws ecr describe-images \
  --repository-name app \
  --image-ids imageTag=${GIT_SHA}
```

**Solutions:**
- Verify ECR repository permissions
- Check task execution role has ECR access
- Verify image tag is correct
- Check VPC endpoints if private subnet

### 3. Secrets/SSM Access Failures

**Error:** `ResourceInitializationError: unable to pull secrets`

**Check:**
```bash
# List secrets the task needs
aws ecs describe-task-definition \
  --task-definition pr-${PR_NUMBER}-rails-app \
  --query 'taskDefinition.containerDefinitions[0].secrets'

# Verify secrets exist
aws ssm get-parameter --name /pr-${PR_NUMBER}/SECRET_NAME
```

**Solutions:**
- Ensure task execution role has SSM:GetParameters
- Verify secrets exist in SSM Parameter Store
- Check secret names match task definition

### 4. Health Check Failures

**Symptoms:**
- Service constantly restarting
- Target group shows unhealthy

**Check:**
```bash
# Test health endpoint
curl -v https://www.pr-${PR_NUMBER}.staging.loanos.net/up

# Check ALB target health
aws elbv2 describe-target-health \
  --target-group-arn $TG_ARN
```

**Common Causes:**
- App not listening on expected port
- Health endpoint returning non-200
- App taking too long to start
- Security group blocking health checker

### 5. Out of Memory (OOM)

**Symptoms:**
- Exit code 137
- Container killed unexpectedly

**Check:**
```bash
# Check task memory limit
aws ecs describe-task-definition \
  --task-definition pr-${PR_NUMBER}-rails-app \
  --query 'taskDefinition.containerDefinitions[0].{Memory:memory,MemoryReservation:memoryReservation}'

# Check memory metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name MemoryUtilization \
  --dimensions Name=ClusterName,Value=pr-${PR_NUMBER} \
  --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 60 \
  --statistics Maximum
```

**Solutions:**
- Increase task memory limit
- Optimize application memory usage
- Check for memory leaks

---

## Service Deployment Issues

### Rolling Deployment Stuck

**Symptoms:**
- Old tasks not draining
- New tasks not starting

**Check:**
```bash
aws ecs describe-services \
  --cluster pr-${PR_NUMBER} \
  --services rails-app \
  --query 'services[0].deployments[].{Id:id,Status:status,Running:runningCount,Pending:pendingCount,Desired:desiredCount}'
```

**Solutions:**
```bash
# Force new deployment
aws ecs update-service \
  --cluster pr-${PR_NUMBER} \
  --service rails-app \
  --force-new-deployment

# Check deployment configuration
aws ecs describe-services \
  --cluster pr-${PR_NUMBER} \
  --services rails-app \
  --query 'services[0].deploymentConfiguration'
```

### Service Events

**Check recent events:**
```bash
aws ecs describe-services \
  --cluster pr-${PR_NUMBER} \
  --services rails-app \
  --query 'services[0].events[0:10].{Time:createdAt,Message:message}' \
  --output table
```

**Common Events:**

| Event | Meaning |
|-------|---------|
| "has started X tasks" | Normal scaling |
| "has stopped X tasks" | Task failures |
| "unable to place task" | Capacity issues |
| "failed ELB health checks" | App unhealthy |

---

## Network Issues

### Container Can't Reach Internet

**Check:**
```bash
# Verify VPC configuration
aws ecs describe-tasks \
  --cluster pr-${PR_NUMBER} \
  --tasks $TASK_ARN \
  --query 'tasks[0].attachments[0].details'
```

**Solutions:**
- Verify NAT Gateway exists (for private subnets)
- Check route tables
- Verify security group egress rules

### Container Can't Reach RDS

**Check:**
```bash
# Check security group rules
aws ec2 describe-security-groups \
  --group-ids $SG_ID \
  --query 'SecurityGroups[0].IpPermissionsEgress'
```

**Solutions:**
- Ensure ECS security group allows egress to RDS port
- Ensure RDS security group allows ingress from ECS
- Verify VPC peering if cross-VPC

---

## Quick Diagnostic Commands

```bash
# Full cluster overview
aws ecs describe-clusters --clusters pr-${PR_NUMBER}

# All services status
aws ecs list-services --cluster pr-${PR_NUMBER} | \
  xargs -I {} aws ecs describe-services --cluster pr-${PR_NUMBER} --services {} \
  --query 'services[].{Name:serviceName,Status:status,Running:runningCount}'

# Recent task failures
aws ecs list-tasks --cluster pr-${PR_NUMBER} --desired-status STOPPED \
  --query 'taskArns[0:5]' --output text | \
  xargs aws ecs describe-tasks --cluster pr-${PR_NUMBER} --tasks \
  --query 'tasks[].{Task:taskArn,Reason:stoppedReason,At:stoppedAt}'
```
