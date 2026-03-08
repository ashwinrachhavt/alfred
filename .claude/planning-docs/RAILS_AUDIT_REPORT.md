# Rails Application Audit Report

**Generated**: 2026-02-06
**Application**: LoanOS Platform
**Rails Version**: 8.1.1
**Ruby Version**: 3.3.5
**Audit Scope**: Targeted - Replyable Document Status Emails Feature

---

## Executive Summary

| Category | Critical | High | Medium | Low | Total |
|----------|----------|------|--------|-----|-------|
| Testing | 0 | 0 | 1 | 0 | 1 |
| Security | 0 | 0 | 0 | 0 | 0 |
| Models | 0 | 0 | 0 | 1 | 1 |
| Controllers | 0 | 0 | 0 | 0 | 0 |
| Code Design | 0 | 1 | 2 | 0 | 3 |
| Views | 0 | 0 | 0 | 0 | 0 |
| **Total** | **0** | **1** | **3** | **1** | **5** |

### Key Findings

1. **[Medium]** Missing test for Email.message_id fallback lookup in InboundEmail
2. **[High]** Agentic module uses Service pattern - consider PORO refactoring
3. **[Medium]** DocumentStatusMailer#status_update is a Long Method (27 lines in main action)
4. **[Medium]** LoisMailbox#process has multiple levels of nesting

---

## 1. Testing Issues

### Overview
- **Test Framework**: RSpec
- **Files with Tests**: 4 / 4 (100%)
- **Estimated Coverage**: High

### Assessment

All modified files have corresponding spec files with comprehensive tests:

| File | Spec File | Coverage |
|------|-----------|----------|
| email_thread.rb | email_thread_spec.rb | Associations, validations, deal validation |
| inbound_email.rb | inbound_email_spec.rb | find_or_create_thread, normalize_message_id |
| document_status_mailer.rb | document_status_mailer_spec.rb | Threading, OutboundEmail creation, headers |
| agentic.rb | agentic_spec.rb | deal_id passing, session context |
| lois_mailbox.rb | lois_mailbox_spec.rb | Deal access validation, rejection flow |

### Medium Severity

#### [T-01] Missing Test for Email.message_id Fallback Lookup

**File**: app/spec/models/inbound_email_spec.rb
**Impact**: Critical code path untested

The `find_or_create_thread` method has a fallback to find threads by `Email.message_id`, but this specific path is not tested. This is the path used when replying to document status emails.

**Code Location** (`inbound_email.rb:59-61`):
```ruby
# Fall back to finding by any email's message_id in the thread
thread = Email.find_by(message_id: thread_root)&.email_thread
return thread if thread
```

**Recommended Test**:
```ruby
context "when references match an existing email message_id" do
  let!(:existing_thread) { create(:email_thread) }
  let!(:existing_email) do
    create(:outbound_email,
      email_thread: existing_thread,
      message_id: "<outbound@example.com>")
  end

  it "finds thread by email message_id" do
    mail = Mail.new do
      from "test@example.com"
      to "lois@loanos.net"
      subject "Re: Test"
      body "Reply"
      message_id "<reply@example.com>"
    end
    allow(mail).to receive(:references).and_return(["<outbound@example.com>"])

    thread = InboundEmail.find_or_create_thread(mail, nil)
    expect(thread).to eq(existing_thread)
  end
end
```

**Status**: **Action Required** - Add test case

---

## 2. Security Issues

### Assessment

**No security issues found.**

Positive findings:
- Deal access validation added to LoisMailbox prevents unauthorized document uploads
- sender_can_access_deal? checks both user membership and invitation status
- No SQL injection (uses ActiveRecord query interface)
- No mass assignment vulnerabilities

---

## 3. Models Issues

### Low Severity

#### [M-01] EmailThread Custom Validation Could Use Rails Validator

**File**: app/app/models/email_thread.rb:20-25
**Impact**: Minor maintainability concern

**Assessment**: The custom validation deal_belongs_to_organization is a valid pattern for cross-model validation. Consider extracting to a custom validator if this pattern is reused elsewhere, but acceptable as-is for a single use case.

**Status**: Acceptable - No action required

---

## 4. Code Design Issues

### High Severity

#### [CD-01] Service Module Pattern - Consider PORO Refactoring

**File**: app/app/services/agentic.rb
**Lines**: 101
**Impact**: Module with class methods obscures domain concept

**Current Pattern**:
```ruby
module Agentic
  def self.process_email(email)
    # ...
  end

  def self.resolve_organization(email)
    # ...
  end
end
```

**Analysis**: The Agentic module uses a procedural service pattern with class methods. Per thoughtbot Ruby Science, this could be refactored to domain models.

**Potential Refactoring**:
```ruby
# app/models/agentic/email_processor.rb
class Agentic::EmailProcessor
  include ActiveModel::Model

  attr_accessor :email, :deal_id

  def process
    return unless valid?
    session = find_or_create_session
    invoke_agent
  end
end
```

**Recommendation**: Consider refactoring if the module grows beyond ~150 lines or gains more responsibilities. Current size (101 lines) is borderline acceptable.

**Status**: Monitor - Consider refactoring in future iteration

---

### Medium Severity

#### [CD-02] Long Method: DocumentStatusMailer#status_update

**File**: app/app/mailers/document_status_mailer.rb:4-31
**Lines**: 27 lines in main method
**Impact**: Method does multiple things (setup, email creation, mail config)

**Assessment**: The method has three distinct responsibilities:
1. Setting up instance variables (lines 5-14)
2. Computing subject (lines 16-20)
3. Creating outbound email and configuring mail (lines 22-30)

**Status**: Consider refactoring if method grows further

---

#### [CD-03] Complex Conditional Flow: LoisMailbox#process

**File**: app/app/mailboxes/lois_mailbox.rb:11-33
**Impact**: Multiple levels of nesting make flow harder to follow

**Assessment**: The method has early return for access denial, then conditional organization resolution, then processing. This is actually a reasonable pattern for mailbox processing where multiple paths exist.

**Status**: Acceptable - Current code is readable and tested

---

## 5. Positive Patterns Observed

1. **Good test coverage**: All modified files have corresponding specs with multiple contexts
2. **Proper validation**: EmailThread validates deal/organization consistency
3. **Race condition handling**: find_or_create_by! with rescue for RecordNotUnique
4. **Security-first**: Access validation added before processing
5. **Follows Rails conventions**: Mailer, mailbox, model patterns used correctly
6. **Idempotent design**: Thread creation is deterministic by deal ID

---

## Recommendations Summary

### Quick Wins (Recommended)

1. [ ] Add test for Email.message_id fallback lookup in `inbound_email_spec.rb` (see [T-01])

### Short-term (Consider for Next Iteration)

1. [ ] Extract DocumentStatusMailer#status_update setup into private methods
2. [ ] Consider extracting mailbox conditional flow to guard clause methods

### Long-term (Technical Debt Monitoring)

1. [ ] Monitor Agentic module size - consider PORO refactoring if it exceeds 150 lines
2. [ ] If more email-processing workflows are added, consider creating an EmailWorkflow base class

---

## Files Analyzed

| Directory | Files Analyzed | Issues Found |
|-----------|----------------|--------------|
| app/models/ | 1 | 1 (Low) |
| app/mailboxes/ | 1 | 1 (Medium) |
| app/mailers/ | 1 | 1 (Medium) |
| app/services/ | 1 | 1 (High) |
| spec/ | 4 | 0 |
| **Total** | **8** | **4** |

---

*Report generated by Rails Audit Skill (thoughtbot Best Practices)*
