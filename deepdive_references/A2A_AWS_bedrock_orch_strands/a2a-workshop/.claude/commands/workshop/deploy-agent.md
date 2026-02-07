# Deploy Workshop Agent

Deploy your agent to AWS ECS and verify integration with the orchestrator.

## Arguments

`<agent-type>` - The agent type to deploy (accommodations, transportation, shopping, entertainment)

## Prerequisites

Before deployment, verify:

```bash
# 1. Agent validated
# Run: /workshop/validate-agent <agent-type>

# 2. AWS credentials configured
aws sts get-caller-identity

# 3. ECR repository exists
aws ecr describe-repositories --repository-names a2a-workshop/<agent-type>-agent

# 4. Resources stack deployed
aws cloudformation describe-stacks --stack-name a2a-workshop-resources
```

## Deployment Steps

### Step 1: Pre-Deployment Validation

Run validation to ensure readiness:

```bash
# Validate implementation
/workshop/validate-agent <agent-type>
```

**Expected**: All validation checks pass.

### Step 2: Run Deployment Script

Execute the deployment script:

```bash
./scripts/deploy-agent.sh <agent-type>-agent
```

**The script performs**:
1. Validates resources stack exists
2. Builds Docker image for linux/amd64
3. Tags image with ECR repository URL
4. Pushes image to ECR
5. Deploys service CloudFormation stack
6. Waits for service to become stable

**Expected Output**:
```
=== Deploying Agent: <agent-type>-agent ===

Step 1: Checking prerequisites...
✓ Resources stack exists
✓ ECR repository exists
✓ Service configuration found

Step 2: Building Docker image...
[Docker build output...]
✓ Image built successfully

Step 3: Pushing to ECR...
✓ Image pushed to ECR

Step 4: Deploying service stack...
✓ Stack create/update initiated

Step 5: Waiting for stability...
✓ Service is stable with 1/1 tasks running

=== Deployment Complete ===
Service URL: http://<load-balancer-url>
CloudMap Service: <agent-type>-agent
```

### Step 3: Verify Deployment

#### 3.1 Check ECS Service Status

```bash
aws ecs describe-services \
  --cluster a2a-workshop-workshop \
  --services a2a-workshop-<agent-type>-agent \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'
```

**Expected**:
```json
{
  "Status": "ACTIVE",
  "Running": 1,
  "Desired": 1
}
```

#### 3.2 Check CloudMap Registration

```bash
# Get namespace ID
NAMESPACE_ID=$(aws servicediscovery list-namespaces \
  --query "Namespaces[?Name=='a2a-workshop.local'].Id" \
  --output text)

# List services
aws servicediscovery list-services \
  --filters Name=NAMESPACE_ID,Values=$NAMESPACE_ID \
  --query "Services[?Name=='<agent-type>-agent'].{Name:Name,Id:Id}"
```

**Expected**: Service should be registered with name `<agent-type>-agent`.

#### 3.3 Check Health Endpoint

Get load balancer URL:

```bash
aws cloudformation describe-stacks \
  --stack-name a2a-workshop-resources \
  --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerDNS'].OutputValue" \
  --output text
```

Test agent health:

```bash
LB_URL=<load-balancer-url>
curl http://$LB_URL/<agent-type>-agent/health
```

**Expected**:
```json
{
  "status": "healthy",
  "agent": "<agent-type>-agent",
  "timestamp": "2025-10-23T..."
}
```

#### 3.4 Check Agent Card

```bash
curl http://$LB_URL/<agent-type>-agent/.well-known/agent.json
```

**Expected**:
```json
{
  "id": "<agent-type>-agent",
  "name": "<Agent-Type> Agent",
  "description": "...",
  "skills": [
    {
      "id": "get-<agent-type>",
      "name": "Get <Agent-Type>",
      "description": "..."
    }
  ]
}
```

### Step 4: Test with Orchestrator

#### 4.1 Test Direct Agent Call

```bash
curl -X POST http://$LB_URL/<agent-type>-agent/message/send \
  -H "Content-Type: application/json" \
  -d '{
    "task": {
      "id": "test-123",
      "contextId": "test-ctx",
      "kind": "task",
      "status": {"state": "submitted"},
      "history": [{
        "role": "user",
        "parts": [{"kind": "text", "text": "Get <domain> info for Seattle"}],
        "messageId": "msg-1",
        "kind": "message",
        "taskId": "test-123",
        "contextId": "test-ctx"
      }],
      "input": {"location": "Seattle"},
      "artifacts": []
    }
  }'
```

**Expected**: JSON response with agent data in artifacts.

#### 4.2 Test via Orchestrator

Use the test script:

```bash
./test_mcp_gateway.sh
```

**Test Query**: "Where should I stay in Seattle?"

**Expected Output (Before Your Agent)**:
```
Orchestrator Response:
Based on weather, events, and restaurant data...
[No hotel information]
```

**Expected Output (After Your Agent)**:
```
Orchestrator Response:
Based on current conditions and available accommodations...

Hotels in Seattle:
• Hotel Seattle - $200/night (Rating: 4.5/5)
• Downtown Inn - $150/night (Rating: 4.2/5)
...
```

#### 4.3 Test via MCP Gateway (Claude Code)

In Claude Code, ask:

```
Where should I stay in Seattle this weekend?
```

**Expected**: Response should include hotel recommendations from your agent.

### Step 5: Verify in CloudWatch Logs

Check agent logs:

```bash
aws logs tail /ecs/a2a-workshop/workshop/<agent-type>-agent \
  --since 10m \
  --follow
```

**Look for**:
- Agent startup messages
- CloudMap registration confirmation
- Capability registration
- Incoming request processing
- Response generation

**Example Log Entries**:
```
INFO - Starting <agent-type>-agent
INFO - Registered 1 capabilities
INFO - CloudMap registration successful: <agent-type>-agent
INFO - Processing <agent-type>-agent request for location: Seattle
INFO - Generated response with 5 <domain> options
```

Check orchestrator logs:

```bash
aws logs tail /ecs/a2a-workshop/workshop/orchestrator \
  --since 10m \
  --follow
```

**Look for**:
- Agent discovery including your agent
- Query decomposition selecting your agent
- Parallel agent invocation including your agent
- Response synthesis combining results

**Example Log Entries**:
```
INFO - Discovered 5 agents: weather-agent, events-agent, restaurant-agent, <agent-type>-agent, mcp-gateway
INFO - Selected agents: [weather-agent (95), events-agent (90), <agent-type>-agent (88)]
INFO - Invoking 3 agents in parallel
INFO - Successfully received responses from 3 agents
INFO - Synthesizing response from multiple agents
```

## Verification Checklist

After deployment, verify:

- [ ] ECS service shows 1/1 tasks running
- [ ] CloudMap service registered
- [ ] Health endpoint returns 200 OK
- [ ] Agent card accessible at `/.well-known/agent.json`
- [ ] Direct agent call returns valid A2A response
- [ ] Orchestrator discovers agent in CloudMap
- [ ] Orchestrator selects agent for relevant queries
- [ ] Orchestrator receives and combines agent responses
- [ ] MCP Gateway queries include agent data
- [ ] CloudWatch logs show successful processing
- [ ] Before/after comparison shows clear impact

## Multi-Agent Coordination Test

Test complex queries that require multiple agents:

### Query 1: Simple Accommodations

```
Where should I stay in Seattle?
```

**Expected Agents**: weather, events, restaurants, **accommodations**

### Query 2: Budget Accommodations

```
Find hotels under $200 in Seattle
```

**Expected Agents**: **accommodations** (primary)

### Query 3: Multi-Factor Recommendation

```
Find hotels under $200 near Pike Place Market with free breakfast
```

**Expected Agents**: **accommodations**, restaurants (for nearby dining context)

### Query 4: Weather-Aware Planning

```
Where should I stay in Seattle this weekend if it's raining?
```

**Expected Agents**: weather, events, **accommodations**, restaurants (indoor focus)

## Troubleshooting

### Service Won't Start

**Check**: ECS task logs in CloudWatch

```bash
aws ecs describe-tasks \
  --cluster a2a-workshop-workshop \
  --tasks $(aws ecs list-tasks --cluster a2a-workshop-workshop \
    --service-name a2a-workshop-<agent-type>-agent \
    --query 'taskArns[0]' --output text)
```

**Common Issues**:
- Image pull errors → Check ECR permissions
- Port binding errors → Verify port 8000 in Dockerfile and config
- Import errors → Verify all directories copied in Dockerfile

### CloudMap Registration Fails

**Check**: Agent startup logs

**Common Issues**:
- Wrong namespace ID → Verify `CLOUDMAP_NAMESPACE_ID` env var
- IAM permissions → Verify task role has `servicediscovery:RegisterInstance`
- Service already exists → Deregister and retry

### Orchestrator Doesn't Discover Agent

**Check**: Orchestrator logs during query processing

**Common Issues**:
- Agent card not accessible → Verify `/.well-known/agent.json` endpoint
- Wrong CloudMap service name → Must match agent ID in card
- Health check failing → Verify `/health` endpoint returns 200

### Agent Not Selected for Queries

**Check**: Orchestrator query decomposition logs

**Common Issues**:
- Capability description too narrow → Broaden tags and description
- Wrong tags → Use relevant domain terms (hotels, lodging, accommodations)
- Agent card not descriptive → Enhance description with keywords

### Agent Returns Errors

**Check**: Agent logs in CloudWatch

**Common Issues**:
- Mock data not found → Verify `data/mock/<agent-type>/` exists in image
- Wrong data format → Verify `_format_response()` handles data structure
- Exception in processing → Check error logs for stack trace

## Success Criteria

Deployment is successful when:

1. ✅ Service runs 1/1 tasks
2. ✅ Health check passes
3. ✅ Agent card accessible
4. ✅ Direct calls work
5. ✅ Orchestrator discovers agent
6. ✅ Orchestrator selects agent for relevant queries
7. ✅ Orchestrator includes agent data in responses
8. ✅ Before/after comparison shows clear improvement
9. ✅ Logs show successful processing
10. ✅ Multi-agent queries work correctly

## Next Steps

After successful deployment:

1. **Test Thoroughly**: Run multiple queries to verify behavior
2. **Review Logs**: Check CloudWatch for any warnings or errors
3. **Test Edge Cases**: Try queries with no results, invalid locations, etc.
4. **Document Learnings**: Note what worked well and what was challenging
5. **Celebrate**: You've successfully extended the inter-agent system!

## Clean Up (Optional)

To remove your agent:

```bash
# Delete service stack
aws cloudformation delete-stack --stack-name a2a-workshop-<agent-type>-agent

# Wait for deletion
aws cloudformation wait stack-delete-complete --stack-name a2a-workshop-<agent-type>-agent
```

Note: This does NOT delete the Docker image in ECR or the ECR repository.
