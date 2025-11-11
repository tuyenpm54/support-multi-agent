# PRD.md - Product Requirements Document

## Multi-Agent Customer Support System for Specific Domain

**Version:** 1.0  
**Date:** November 10, 2024  
**Status:** Draft

---

## 1. EXECUTIVE SUMMARY

### 1.1 Product Vision
Xây dựng hệ thống customer support tự động hóa sử dụng multi-agent architecture để xử lý các vấn đề trong specific domain (ví dụ: Restaurant Management System, Hospital Information System). Hệ thống có khả năng tự động phân loại, thu thập thông tin, kiểm chứng và khắc phục lỗi mà không cần kiến thức về domain từ LLM.

### 1.2 Core Principle
**AI không thể tự phân tích domain-specific issues** → Hệ thống phải dựa vào **pre-defined issue database** được xây dựng từ historical conversations và domain expertise.

### 1.3 Key Metrics
- **Resolution Rate:** ≥ 80% issues tự động giải quyết
- **User Satisfaction:** ≥ 4.2/5
- **Time to Resolution:** < 3 minutes (median)
- **Escalation Rate:** < 15%
- **False Positive Rate:** < 5%
- **Cost per Resolution:** < $0.015

---

## 2. PROBLEM STATEMENT

### 2.1 Current Pain Points
1. **Domain Complexity:**
   - LLM không có kiến thức về specific business domain
   - Không biết entities, relationships, business rules của hệ thống
   - Không thể tự động chẩn đoán lỗi kỹ thuật

2. **Manual Support Inefficiency:**
   - Support agents xử lý manual từng ticket
   - Phải hỏi nhiều câu để thu thập thông tin
   - Repeat công việc tương tự cho cùng loại issue

3. **Knowledge Fragmentation:**
   - Tribal knowledge nằm trong đầu support agents
   - Documentation không đầy đủ hoặc outdated
   - Không có single source of truth

### 2.2 Target Users
- **Primary:** End users của domain-specific system (nhà hàng, bệnh viện, retail, etc.)
- **Secondary:** Support agents (nhận escalated cases)
- **Tertiary:** System administrators (maintain issue database)

---

## 3. SOLUTION OVERVIEW

### 3.1 Two-Flow Architecture

#### Flow 1: Operational Flow (Real-time Issue Resolution)
```
User Report → Classify → Gather Info → Validate → Fix → Response
              (pattern)   (entities)   (confirm)  (execute)
```

**Purpose:** Giải quyết vấn đề user ngay lập tức  
**Latency Target:** < 45 seconds  
**Coverage:** 80-90% common issues

#### Flow 2: Knowledge Extraction Flow (Background Learning)
```
Historical Conversations → Extract Patterns → Build Issue Database
     (batch nightly)         (agents analyze)    (auto-populate)
```

**Purpose:** Tự động học từ past conversations  
**Frequency:** Daily/Weekly batch processing  
**Coverage Improvement:** +5-10% per month

### 3.2 Four-Agent System (Operational Flow)
```
┌─────────────────────────────────────────────────┐
│              ORCHESTRATOR                       │
│  (Coordinator, State Manager, Decision Maker)  │
└─────────────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┬──────────────┐
        │             │             │              │
        ▼             ▼             ▼              ▼
┌─────────────┐ ┌────────────┐ ┌────────┐ ┌──────────┐
│ CLASSIFIER  │ │ REQUIRED   │ │VALIDATE│ │   FIX    │
│   AGENT     │ │INFO AGENT  │ │ AGENT  │ │  AGENT   │
└─────────────┘ └────────────┘ └────────┘ └──────────┘
      │                │            │           │
      ▼                ▼            ▼           ▼
[Issue DB]    [Lookup Tools]  [Check    [Action
               [Database]      Tools]     Tools]
```

---

## 4. DETAILED REQUIREMENTS

### 4.1 Classifier Agent

**Objective:** Phân loại user input thành specific issue pattern từ database

**Input:**
- User message (natural language)
- User metadata (role, location, system version)
- Conversation history (optional)

**Process:**
1. Semantic search trong issue database (vector similarity)
2. Extract entities từ user message
3. Match với issue patterns
4. Return classification với confidence score

**Output:**
```json
{
  "matched_issue": {
    "issue_id": "MENU_VIS_001",
    "issue_name": "Món không hiển thị trong menu",
    "confidence": 0.93,
    "category": "menu_management"
  },
  "extracted_entities": {
    "item_name": "Phở bò",
    "item_code": null
  }
}
```

**Success Criteria:**
- Confidence ≥ 0.85: Proceed
- 0.65 ≤ Confidence < 0.85: Ask diagnostic question
- Confidence < 0.65: Escalate or re-clarify

**Performance:**
- Latency: < 3 seconds (p95)
- Accuracy: > 90% (on test set)
- Token usage: ~500 tokens per call

---

### 4.2 Required Info Agent

**Objective:** Thu thập đầy đủ thông tin cần thiết để xử lý issue

**Input:**
- Matched issue (với required_fields definition)
- Extracted entities từ Classifier
- Database lookup tools

**Process:**
1. Identify missing required fields
2. For each missing field:
   - If user provided name → Call lookup tool
   - Else → Ask user directly
3. Handle multiple matches (present options)
4. Validate collected info (regex, format)

**Tools Available:**
- `lookup_item(name, code, fuzzy)` → Find items
- `lookup_warehouse(name, code, location)` → Find warehouses
- `lookup_menu(name, code, active_only)` → Find menus
- Custom domain-specific lookup tools

**Multi-turn Conversation:**
```
Bot: "Để kiểm tra, tôi cần biết:
     1. Món nào không hiển thị?
     2. Ở kho nào?"

User: "Món Phở bò, kho chi nhánh 1"

Bot: [Calls lookup_item("Phở bò")]
     "Tìm thấy 2 món:
      1. Phở bò đặc biệt (ITEM_001)
      2. Phở bò tái (ITEM_002)
      Chọn món nào?"

User: "Món 1"

Bot: [Confirms] "Đã đủ thông tin, đang kiểm tra..."
```

**Success Criteria:**
- Complete info gathering in ≤ 3 turns (80% cases)
- Lookup accuracy: > 95%
- User abandonment rate: < 10%

**Performance:**
- Latency: < 2 seconds per turn (p95)
- Token usage: ~300 tokens per turn

---

### 4.3 Validate Agent

**Objective:** Kiểm chứng issue thực sự tồn tại và đúng như classified

**Input:**
- Matched issue
- Complete info (entities)
- Validation tools từ issue database (max 5 tools)

**Process:**
1. Execute validation tools theo priority order
2. Compare actual state vs expected state
3. Early exit nếu detect false positive
4. Return validation result

**Tool Execution:**
```json
{
  "validation_tools": [
    {
      "tool_name": "check_item_exists",
      "priority": 1,
      "params": {"item_code": "{item_code}"},
      "expected_result": {"exists": true},
      "if_fail": "ITEM_NOT_FOUND"
    },
    {
      "tool_name": "check_item_menu_link",
      "priority": 2,
      "params": {"item_code": "{item_code}", "menu_id": "{menu_id}"},
      "expected_result": {"linked": false},
      "if_fail": "ALREADY_LINKED"
    }
  ]
}
```

**Possible Outcomes:**
- **CONFIRMED (90%):** Issue verified, proceed to fix
- **NOT_FOUND (5%):** False positive, inform user
- **DIFFERENT_ISSUE (3%):** Re-classify to detected issue
- **UNCERTAIN (2%):** Escalate to human

**Success Criteria:**
- Validation accuracy: > 92%
- False positive detection: > 95%
- No false negatives: Critical

**Performance:**
- Latency: < 5 seconds (p95)
- Token usage: ~800 tokens

---

### 4.4 Fix Agent

**Objective:** Thực hiện actions để khắc phục issue

**Input:**
- Validated issue
- Complete info
- Fix tools từ issue database (max 5 tools)

**Process:**
1. Review fix tools và permission requirements
2. Request user permission (if needed)
3. Execute tools theo execution_order
4. Capture state for rollback
5. Verify fix successful

**Tool Execution:**
```json
{
  "fix_tools": [
    {
      "tool_name": "link_item_to_menu",
      "execution_order": 1,
      "params": {"item_code": "{item_code}", "menu_id": "{menu_id}"},
      "permission_level": "user_confirmation",
      "reversible": true,
      "rollback_tool": "unlink_item_from_menu",
      "risk_level": "low"
    },
    {
      "tool_name": "refresh_menu_cache",
      "execution_order": 2,
      "params": {"menu_id": "{menu_id}"},
      "permission_level": "auto",
      "reversible": false
    }
  ]
}
```

**Permission Levels:**
- **auto:** Execute immediately (low-risk)
- **user_confirmation:** Ask user approval
- **supervisor_approval:** Need manager approval
- **manual_only:** Escalate to technical team

**Rollback Capability:**
- Capture pre-fix state
- Store rollback token (valid 24h)
- Allow user to undo changes
- Auto-rollback on unexpected side effects

**Possible Outcomes:**
- **SUCCESS:** All actions completed
- **PARTIAL:** Some actions failed (non-critical)
- **FAILED:** Critical action failed, rolled back
- **PERMISSION_DENIED:** User declined

**Success Criteria:**
- Fix success rate: > 85%
- Rollback success rate: > 98%
- No data corruption: Critical

**Performance:**
- Latency: < 10 seconds (simple), < 30 seconds (complex)
- Token usage: ~400 tokens

---

### 4.5 Orchestrator Agent

**Objective:** Điều phối workflow, manage state, handle errors

**Responsibilities:**
1. **State Management:**
   - Maintain session state throughout conversation
   - Track current phase (CLASSIFY → INFO → VALIDATE → FIX)
   - Store timeline of actions
   - Manage conversation history

2. **Decision Making:**
   - Route to appropriate agent based on phase
   - Handle agent failures and retries
   - Decide when to escalate to human
   - Manage fallback strategies

3. **User Communication:**
   - Generate user-friendly responses
   - Provide progress updates (real-time)
   - Request permissions/confirmations
   - Handle user interruptions

4. **Error Handling:**
   - Agent timeouts → Retry or fallback
   - Tool failures → Alternative approaches
   - Invalid state transitions → Prevent
   - Concurrent conflicts → Resolve

**Session State Schema:**
```json
{
  "session_id": "SESSION_...",
  "user_id": "USER_...",
  "current_phase": "VALIDATE",
  "classification": {...},
  "required_info": {...},
  "validation": {...},
  "fix": {...},
  "timeline": [...],
  "conversation_history": [...],
  "fallback_count": 0,
  "retry_count": 0
}
```

**Decision Points:**
- After Classification: Proceed vs Ask clarification vs Escalate
- After Required Info: Complete vs Continue gathering vs Timeout
- After Validation: Fix vs Re-classify vs Escalate
- After Fix: Success vs Retry vs Rollback vs Escalate

**Performance:**
- Session management overhead: < 100ms
- State persistence: Redis (in-memory)
- Token usage: ~2,000 tokens for synthesis

---

## 5. ISSUE DATABASE STRUCTURE

### 5.1 Issue Pattern Schema
```json
{
  "issue_id": "MENU_VIS_001",
  "issue_name": "Món không hiển thị trong menu",
  "category": "menu_management",
  "description": "Item exists but not visible in branch menu",
  
  "embedding": [0.123, 0.456, ...],
  
  "required_fields": [
    {
      "field": "item_code",
      "type": "string",
      "required": true,
      "lookup_tool": "lookup_item",
      "validation_regex": "^ITEM_[0-9]+$"
    },
    {
      "field": "warehouse_code",
      "type": "string",
      "required": true,
      "lookup_tool": "lookup_warehouse"
    }
  ],
  
  "validation_tools": [
    {
      "tool_name": "check_item_exists",
      "priority": 1,
      "params": {"item_code": "{item_code}"},
      "expected_result": {"exists": true},
      "if_fail": "ITEM_NOT_FOUND"
    }
  ],
  
  "fix_tools": [
    {
      "tool_name": "link_item_to_menu",
      "execution_order": 1,
      "params": {"item_code": "{item_code}", "menu_id": "{menu_id}"},
      "permission_level": "user_confirmation",
      "reversible": true,
      "rollback_tool": "unlink_item_from_menu"
    }
  ],
  
  "max_validation_tools": 5,
  "max_fix_tools": 5,
  
  "historical_metrics": {
    "occurrence_count": 127,
    "resolution_rate": 0.89,
    "avg_resolution_time_seconds": 420
  }
}
```

### 5.2 Tool Registry Schema
```json
{
  "tool_name": "lookup_item",
  "type": "lookup",
  "description": "Search items by name or code",
  
  "params": {
    "name": {"type": "string", "required": false},
    "code": {"type": "string", "required": false},
    "fuzzy": {"type": "boolean", "default": true}
  },
  
  "returns": {
    "matches": "array[object]",
    "total_matches": "integer"
  },
  
  "implementation": "api_endpoint",
  "endpoint": "/api/v1/items/search",
  "timeout_seconds": 5,
  "rate_limit": "100/minute",
  "avg_latency_ms": 120
}
```

### 5.3 Database Requirements

**Issue Patterns Table:**
- 20-50 common issues initially
- Expandable to 200+ issues
- Vector search capability (pgvector or similar)
- Update frequency: Weekly (from extraction flow)

**Tool Registry:**
- 15-30 tools per domain
- Versioned (support tool upgrades)
- Monitoring metrics (latency, success rate)

**Conversations Archive:**
- Store resolved conversations
- For knowledge extraction flow
- Retention: 1 year

---

## 6. USER EXPERIENCE REQUIREMENTS

### 6.1 Conversation Flow

**Ideal Path (90% target):**
```
User: "Món A không hiển thị"
  ↓ [2s]
Bot: "Để kiểm tra, món nào và ở kho nào?"
  ↓
User: "Món Phở bò, kho chi nhánh 1"
  ↓ [5s - lookup + validate]
Bot: "Phát hiện món chưa được liên kết với menu.
     Tôi có thể khắc phục ngay. Bạn đồng ý không?
     [Đồng ý] [Xem chi tiết]"
  ↓
User: [Clicks Đồng ý]
  ↓ [5s - fix]
Bot: "✅ Đã khắc phục! Món giờ đã hiển thị trong menu.
     Bạn có thể kiểm tra lại."
     
Total time: ~15 seconds, 3 turns
```

**Edge Case Handling:**
```
Scenario: User không biết tên chính xác
Bot: "Có 8 món chứa 'phở'. Bạn có thể cung cấp thêm chi tiết?"
  → Narrow down progressively

Scenario: Issue không thể tự động fix
Bot: "Vấn đề này cần technical team xử lý.
     Tôi đã tạo ticket TECH-12345.
     Bạn sẽ nhận update trong 2 giờ."
  → Graceful escalation

Scenario: User thay đổi ý
Bot: "Tôi có thể hoàn tác thay đổi vừa rồi. Bạn chắc chứ?"
  → Allow rollback
```

### 6.2 Real-time Progress Updates

**Implementation: Server-Sent Events (SSE)**
```
[10:30:00] User: "Món không hiển thị"
[10:30:02] Bot: "⏳ Đang phân tích vấn đề..."
[10:30:05] Bot: "✅ Phân loại: Món chưa liên kết với menu"
[10:30:07] Bot: "🔍 Cần thêm thông tin..."
[10:30:20] Bot: "⏳ Đang kiểm tra hệ thống..."
[10:30:25] Bot: "✅ Xác nhận vấn đề"
[10:30:30] Bot: "🔧 Đang khắc phục..."
[10:30:35] Bot: "✅ Hoàn thành!"
```

**Benefits:**
- User không cảm thấy "treo máy"
- Transparency về process
- Build trust

### 6.3 Mobile & Desktop Support

**Requirements:**
- Responsive design
- Touch-friendly buttons (min 44x44px)
- Copy-paste support (for codes)
- Attachment support (screenshots)
- Offline detection (queue messages)

---

## 7. NON-FUNCTIONAL REQUIREMENTS

### 7.1 Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| Classification latency | < 3s (p95) | Per agent call |
| Info gathering per turn | < 2s (p95) | Per agent call |
| Validation latency | < 5s (p95) | Per agent call |
| Fix latency (simple) | < 10s (p95) | Per agent call |
| Total resolution time | < 45s (p90) | End-to-end |
| Concurrent sessions | 100+ | Per server instance |
| Database query latency | < 200ms (p95) | Tool calls |

### 7.2 Scalability

**Horizontal Scaling:**
- Stateless agents (can scale independently)
- State stored in Redis (distributed)
- Database with connection pooling
- Load balancer for traffic distribution

**Capacity Planning:**
- 1,000 concurrent users per region
- 10,000 requests per day (initially)
- 100,000 requests per day (6 months)

### 7.3 Reliability

**Availability:**
- Target: 99.5% uptime (43.8 minutes downtime/month)
- Graceful degradation: Fallback to human when system down
- Health checks every 30 seconds

**Error Handling:**
- Agent timeout: Retry once, then fallback
- Tool failure: Retry with exponential backoff
- Database error: Use cached data or escalate
- LLM API error: Queue request, notify user of delay

**Data Integrity:**
- Atomic transactions for critical operations
- Rollback capability for fixes
- Audit log for all actions
- No data loss on failures

### 7.4 Security

**Authentication:**
- User authentication via OAuth 2.0
- Session tokens (JWT) with 30-minute expiry
- Role-based access control (RBAC)

**Authorization:**
- Permission checks before fix actions
- Tool-level permissions
- Audit log of who did what

**Data Privacy:**
- PII filtering in logs
- Conversation history encrypted at rest
- GDPR compliance (data deletion on request)

**Rate Limiting:**
- Per user: 20 requests/minute
- Per IP: 100 requests/minute
- Tool calls: Tool-specific limits

### 7.5 Observability

**Logging:**
- Structured logs (JSON format)
- Log levels: DEBUG, INFO, WARN, ERROR, CRITICAL
- Retention: 90 days (hot), 1 year (cold)

**Metrics:**
- Business metrics (resolution rate, satisfaction, etc.)
- Technical metrics (latency, errors, token usage)
- Dashboard with real-time updates
- Alerting on anomalies

**Tracing:**
- Distributed tracing (OpenTelemetry)
- Trace each request through all agents
- Correlation IDs for debugging

---

## 8. COST STRUCTURE

### 8.1 LLM API Costs

**Token Usage per Request:**
- Classifier: 500 tokens
- Required Info: 300 tokens × 2 turns = 600 tokens
- Validate: 800 tokens
- Fix: 400 tokens
- Orchestrator synthesis: 2,000 tokens
- **Total: ~4,300 tokens per request**

**Pricing (Claude Sonnet 4):**
- Input: $3 per 1M tokens
- Output: $15 per 1M tokens
- Average: ~$0.013 per request

**Monthly Cost (10K requests/day):**
- 10,000 × 30 = 300,000 requests/month
- 300,000 × $0.013 = **$3,900/month**

### 8.2 Infrastructure Costs

**Compute:**
- Application servers: 2 instances × $100/month = $200
- Redis (state storage): $50/month
- PostgreSQL (database): $100/month
- Load balancer: $50/month
- **Total: $400/month**

**Storage:**
- Issue database: ~1GB = $5/month
- Conversation archives: ~10GB/month = $10/month
- Logs: ~20GB/month = $20/month
- **Total: $35/month**

**Total Infrastructure: $435/month**

### 8.3 Total Cost

**Monthly (10K requests/day):**
- LLM API: $3,900
- Infrastructure: $435
- **Total: $4,335/month**

**Cost per Resolution:**
- $4,335 / 300,000 = **$0.014 per request**

**Cost Comparison:**
- Human agent cost: ~$2-5 per ticket
- Automation savings: 99.3%-99.7% cost reduction
- ROI: Break-even at ~2,000 requests/month

---

## 9. SUCCESS CRITERIA

### 9.1 Launch Criteria (MVP)

**Must Have:**
- [ ] 20+ common issues in database
- [ ] 4 agents operational (Classifier, Required Info, Validate, Fix)
- [ ] Orchestrator managing workflow
- [ ] 10+ tools implemented and tested
- [ ] Resolution rate ≥ 70%
- [ ] Latency < 60 seconds (p90)
- [ ] Escalation path to human working

**Should Have:**
- [ ] Real-time progress updates
- [ ] Rollback capability
- [ ] Audit logging
- [ ] Basic monitoring dashboard

**Nice to Have:**
- [ ] Knowledge extraction flow
- [ ] A/B testing framework
- [ ] Advanced analytics

### 9.2 Success Metrics (3 months post-launch)

| Metric | Target | Current (baseline) |
|--------|--------|--------------------|
| Resolution rate | ≥ 80% | N/A (new system) |
| User satisfaction | ≥ 4.2/5 | 3.5/5 (human agents) |
| Time to resolution | < 3 min | 15 min (human agents) |
| Escalation rate | < 15% | 100% (all manual) |
| Cost per resolution | < $0.02 | $3.50 (human agents) |
| Coverage (issues in DB) | ≥ 80% | 0% |

### 9.3 Continuous Improvement Goals

**Month 1-3:**
- Expand issue database to 50 patterns
- Achieve 75% resolution rate
- Reduce latency to < 45 seconds

**Month 4-6:**
- Implement knowledge extraction flow
- Achieve 85% resolution rate
- Expand to 100+ issue patterns

**Month 7-12:**
- Multi-language support
- 90% resolution rate
- Proactive issue detection

---

## 10. RISKS & MITIGATION

### 10.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| LLM API downtime | Medium | High | Fallback to human, queue requests |
| Classification accuracy < 90% | Medium | High | Continuous tuning, human-in-the-loop |
| Tool failures | High | Medium | Retry logic, monitoring, graceful degradation |
| Database performance | Low | High | Indexing, caching, query optimization |
| Scale limitations | Medium | Medium | Load testing, horizontal scaling plan |

### 10.2 Business Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| User adoption low | Medium | High | Training, onboarding, feedback loop |
| Issue database outdated | High | High | Knowledge extraction flow, regular review |
| Cost overruns | Low | Medium | Token optimization, usage monitoring |
| Regulatory compliance | Low | High | Privacy by design, audit trail |

### 10.3 User Experience Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Users frustrated with multi-turn | Medium | Medium | Minimize turns, provide shortcuts |
| Users don't trust automation | Medium | High | Transparency, allow human override |
| Users confused by technical terms | High | Medium | Plain language, context help |

---

## 11. LAUNCH PLAN

### 11.1 Phase 1: Shadow Mode (Week 1-2)
- Run system parallel with human agents
- No auto-fix, only log recommendations
- Collect accuracy and performance data
- **Goal:** 85% classification accuracy

### 11.2 Phase 2: Assisted Mode (Week 3-4)
- System suggests fixes to human agents
- Human reviews before execution
- Learn from human corrections
- **Goal:** 90% of suggestions approved

### 11.3 Phase 3: Supervised Auto-fix (Week 5-8)
- Auto-fix for low-risk issues (user confirmation)
- Medium/high-risk require supervisor approval
- 24/7 monitoring
- **Goal:** 70% resolution rate

### 11.4 Phase 4: Full Automation (Week 9+)
- Auto-fix for majority of issues
- Escalate only complex cases
- Knowledge extraction flow activated
- **Goal:** 80% resolution rate

---

## 12. APPENDIX

### 12.1 Glossary

- **Issue Pattern:** Pre-defined problem type với validation và fix logic
- **Entity:** Domain object (item, warehouse, menu, etc.)
- **Tool:** Function để interact với system (lookup, check, fix)
- **Confidence:** Score 0-1 indicating classification certainty
- **Rollback:** Undo changes made by fix agent
- **Escalation:** Transfer to human agent when automation fails

### 12.2 References

- Architecture Document (architecture.md)
- API Specification (api-spec.yaml)
- Tool Registry (tools.json)
- Issue Database Schema (schema.sql)

---

**Document Control:**
- **Author:** System Architect
- **Reviewers:** Product Manager, Engineering Lead, Domain Expert
- **Next Review:** December 10, 2024
- **Version History:**
  - v1.0 (Nov 10, 2024): Initial draft