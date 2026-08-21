"""Generate the reproducible enterprise-policy RAG benchmark package.

The catalog contains no customer records. It is a controlled, template-based
proxy for anonymized enterprise policy traffic and must not be described as a
production dataset until reviewed source material is substituted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "refunds",
        "domain": "customer_support",
        "supported_query": "Within how many days may a standard customer request a refund?",
        "supported_evidence": "Standard customers may request a refund within 30 calendar days of purchase.",
        "supported_answer": "The standard refund window is 30 calendar days.",
        "contradicted_query": "May a contractor export customer data to an external analytics vendor?",
        "contradicted_evidence": "Contractors must not export customer data to an external analytics vendor.",
        "contradicted_answer": "Yes, the contractor may export the customer data.",
        "insufficient_query": "What retention period applies to archived customer records?",
        "partial_query": "What refund windows apply to standard and premium customers?",
        "partial_evidence": "Standard customers may request a refund within 30 calendar days of purchase.",
        "distractors": [
            "Premium support requests are reviewed within two business days.",
            "Support agents may update customer account notes after identity verification.",
            "Shipping claims must include the order reference and delivery date.",
        ],
    },
    {
        "id": "retention",
        "domain": "records_management",
        "supported_query": "How long are closed support tickets retained?",
        "supported_evidence": "Closed support tickets are retained for 24 months after closure.",
        "supported_answer": "Closed support tickets are retained for 24 months.",
        "contradicted_query": "May an analyst delete a legal hold record before the hold is released?",
        "contradicted_evidence": "Analysts must not delete a legal hold record before the hold is released.",
        "contradicted_answer": "Yes, the analyst may delete the legal hold record.",
        "insufficient_query": "What is the retention period for archived security camera footage?",
        "partial_query": "What retention periods apply to support tickets and legal hold records?",
        "partial_evidence": "Closed support tickets are retained for 24 months after closure.",
        "distractors": [
            "Archived billing statements remain available in the customer portal.",
            "Legal hold notices are reviewed by the records management owner.",
            "Support tickets may be reopened when a customer supplies new evidence.",
        ],
    },
    {
        "id": "access_control",
        "domain": "identity_and_access",
        "supported_query": "Which approval is required before a privileged role is granted?",
        "supported_evidence": "A privileged role requires approval from the system owner and the security team.",
        "supported_answer": "Both the system owner and security team must approve the privileged role.",
        "contradicted_query": "Can a manager share a privileged account password with a contractor?",
        "contradicted_evidence": "Managers must not share privileged account passwords with contractors.",
        "contradicted_answer": "Yes, the manager may share the privileged password.",
        "insufficient_query": "What is the maximum session duration for emergency administrator access?",
        "partial_query": "What approval and session duration rules apply to privileged access?",
        "partial_evidence": "A privileged role requires approval from the system owner and the security team.",
        "distractors": [
            "Standard user access is approved by the employee's line manager.",
            "Emergency administrator access is logged for later review.",
            "Multi-factor authentication is required for remote access.",
        ],
    },
    {
        "id": "privacy_export",
        "domain": "privacy",
        "supported_query": "Where must a data export request be recorded?",
        "supported_evidence": "Every approved data export request must be recorded in the privacy case register.",
        "supported_answer": "Approved exports must be recorded in the privacy case register.",
        "contradicted_query": "May an employee send personal data to an unapproved external recipient?",
        "contradicted_evidence": "Employees must not send personal data to an unapproved external recipient.",
        "contradicted_answer": "Yes, the employee may send the personal data externally.",
        "insufficient_query": "Which retention period applies to biometric templates?",
        "partial_query": "What recording and approval rules apply to data exports and external recipients?",
        "partial_evidence": "Every approved data export request must be recorded in the privacy case register.",
        "distractors": [
            "Data subject requests are routed to the privacy operations queue.",
            "Approved vendors must complete the annual privacy assessment.",
            "Privacy incidents are assigned a severity and response owner.",
        ],
    },
    {
        "id": "incident_response",
        "domain": "security_operations",
        "supported_query": "Who must be notified after a confirmed high severity incident?",
        "supported_evidence": "The incident commander must notify the security director and service owner after a confirmed high severity incident.",
        "supported_answer": "The security director and service owner must be notified.",
        "contradicted_query": "Can an engineer close a high severity incident without incident commander approval?",
        "contradicted_evidence": "Engineers must not close a high severity incident without incident commander approval.",
        "contradicted_answer": "Yes, the engineer may close the incident without approval.",
        "insufficient_query": "What is the notification deadline for a suspected vendor breach?",
        "partial_query": "What notification and closure rules apply to high severity incidents?",
        "partial_evidence": "The incident commander must notify the security director and service owner after a confirmed high severity incident.",
        "distractors": [
            "Low severity incidents are reviewed during the weekly operations meeting.",
            "Incident timelines are attached to the case record after resolution.",
            "Vendor security findings are tracked in the third-party risk register.",
        ],
    },
    {
        "id": "vendor_risk",
        "domain": "third_party_risk",
        "supported_query": "What assessment is required before onboarding a critical vendor?",
        "supported_evidence": "A critical vendor requires a security and privacy risk assessment before onboarding.",
        "supported_answer": "The vendor needs security and privacy risk assessments before onboarding.",
        "contradicted_query": "May procurement onboard a critical vendor before the risk assessment is complete?",
        "contradicted_evidence": "Procurement must not onboard a critical vendor before the risk assessment is complete.",
        "contradicted_answer": "Yes, procurement may onboard the critical vendor immediately.",
        "insufficient_query": "What insurance limit is required for a strategic vendor?",
        "partial_query": "What assessment and insurance requirements apply to critical vendors?",
        "partial_evidence": "A critical vendor requires a security and privacy risk assessment before onboarding.",
        "distractors": [
            "Critical vendors receive a quarterly performance review.",
            "Contract renewals require confirmation of the vendor owner.",
            "Strategic vendors may be included in the continuity exercise plan.",
        ],
    },
    {
        "id": "expense_approval",
        "domain": "finance_operations",
        "supported_query": "Who approves a business expense above the team threshold?",
        "supported_evidence": "Expenses above the team threshold require approval from the department director.",
        "supported_answer": "The department director approves expenses above the team threshold.",
        "contradicted_query": "Can an employee approve their own expense above the team threshold?",
        "contradicted_evidence": "Employees must not approve their own expenses above the team threshold.",
        "contradicted_answer": "Yes, the employee may approve the expense themselves.",
        "insufficient_query": "What currency conversion source applies to international expenses?",
        "partial_query": "What approval and currency rules apply to expenses above the team threshold?",
        "partial_evidence": "Expenses above the team threshold require approval from the department director.",
        "distractors": [
            "Small team expenses can be approved by the line manager.",
            "Receipts are attached to the expense record before submission.",
            "International travel expenses are reviewed after the trip closes.",
        ],
    },
    {
        "id": "travel",
        "domain": "travel_and_expenses",
        "supported_query": "When must international travel be approved?",
        "supported_evidence": "International travel must be approved before the itinerary is booked.",
        "supported_answer": "Approval is required before booking the itinerary.",
        "contradicted_query": "May an employee book international travel before approval?",
        "contradicted_evidence": "Employees must not book international travel before approval is recorded.",
        "contradicted_answer": "Yes, the employee may book international travel first.",
        "insufficient_query": "What hotel rate limit applies to a remote office visit?",
        "partial_query": "What approval and hotel rate rules apply to international travel?",
        "partial_evidence": "International travel must be approved before the itinerary is booked.",
        "distractors": [
            "Domestic travel can be submitted through the standard booking portal.",
            "Travel receipts are uploaded within ten business days after return.",
            "Remote office visits require the destination cost center.",
        ],
    },
    {
        "id": "human_resources",
        "domain": "people_operations",
        "supported_query": "How far in advance should planned leave be requested?",
        "supported_evidence": "Planned leave should be requested at least 10 business days in advance.",
        "supported_answer": "Planned leave should be requested at least 10 business days ahead.",
        "contradicted_query": "Can a manager approve leave without checking team coverage?",
        "contradicted_evidence": "Managers must not approve planned leave without checking team coverage.",
        "contradicted_answer": "Yes, the manager may approve leave without checking coverage.",
        "insufficient_query": "How many caregiver leave days are available in a calendar year?",
        "partial_query": "What notice and caregiver leave rules apply to planned leave?",
        "partial_evidence": "Planned leave should be requested at least 10 business days in advance.",
        "distractors": [
            "Emergency leave is reported to the people operations queue.",
            "Team coverage plans are stored with the quarterly staffing review.",
            "Leave approvals are visible to the employee and their manager.",
        ],
    },
    {
        "id": "support_sla",
        "domain": "service_management",
        "supported_query": "What is the response target for a priority one support ticket?",
        "supported_evidence": "Priority one support tickets have a first response target of one hour.",
        "supported_answer": "The first response target is one hour.",
        "contradicted_query": "May a support agent downgrade a priority one ticket without customer confirmation?",
        "contradicted_evidence": "Support agents must not downgrade a priority one ticket without customer confirmation.",
        "contradicted_answer": "Yes, the agent may downgrade the ticket without confirmation.",
        "insufficient_query": "What resolution target applies to a priority four ticket?",
        "partial_query": "What response and resolution targets apply to priority one and priority four tickets?",
        "partial_evidence": "Priority one support tickets have a first response target of one hour.",
        "distractors": [
            "Priority two tickets are reviewed by the service desk lead.",
            "Customer confirmation is attached to a ticket status change.",
            "Support hours are extended during a planned service event.",
        ],
    },
    {
        "id": "security_mfa",
        "domain": "cybersecurity",
        "supported_query": "Which authentication factor is required for remote privileged access?",
        "supported_evidence": "Remote privileged access requires phishing-resistant multi-factor authentication.",
        "supported_answer": "Phishing-resistant multi-factor authentication is required.",
        "contradicted_query": "Can an administrator bypass multi-factor authentication during routine remote access?",
        "contradicted_evidence": "Administrators must not bypass multi-factor authentication during routine remote access.",
        "contradicted_answer": "Yes, the administrator may bypass multi-factor authentication.",
        "insufficient_query": "What device replacement window applies to a lost security key?",
        "partial_query": "What authentication and device replacement rules apply to remote privileged access?",
        "partial_evidence": "Remote privileged access requires phishing-resistant multi-factor authentication.",
        "distractors": [
            "Remote standard access requires a managed device and current endpoint status.",
            "Lost security keys are reported to the identity operations queue.",
            "Authentication events are retained for security investigation.",
        ],
    },
    {
        "id": "classification",
        "domain": "information_governance",
        "supported_query": "What label is required for restricted customer data?",
        "supported_evidence": "Restricted customer data must carry the Restricted label in the document repository.",
        "supported_answer": "Restricted customer data must carry the Restricted label.",
        "contradicted_query": "May an employee store restricted customer data in a personal drive?",
        "contradicted_evidence": "Employees must not store restricted customer data in a personal drive.",
        "contradicted_answer": "Yes, the employee may store the data in a personal drive.",
        "insufficient_query": "What archival format is required for restricted customer data?",
        "partial_query": "What labeling and archival rules apply to restricted customer data?",
        "partial_evidence": "Restricted customer data must carry the Restricted label in the document repository.",
        "distractors": [
            "Internal documents may use the Internal label when they contain no customer data.",
            "Personal drives are not managed repositories for enterprise records.",
            "Repository owners review classification exceptions each quarter.",
        ],
    },
    {
        "id": "data_quality",
        "domain": "data_governance",
        "supported_query": "Who owns remediation of a critical data quality issue?",
        "supported_evidence": "The data product owner owns remediation of a critical data quality issue.",
        "supported_answer": "The data product owner owns remediation.",
        "contradicted_query": "May an analyst publish a critical dataset without a quality review?",
        "contradicted_evidence": "Analysts must not publish a critical dataset without a quality review.",
        "contradicted_answer": "No, publication requires a quality review.",
        "insufficient_query": "What completeness threshold applies to a critical dataset?",
        "partial_query": "What ownership and completeness rules apply to critical datasets?",
        "partial_evidence": "The data product owner owns remediation of a critical data quality issue.",
        "distractors": [
            "Data stewards document quality dimensions in the catalog.",
            "Quality incidents are linked to the affected data product.",
            "Critical datasets receive a monthly monitoring review.",
        ],
    },
    {
        "id": "procurement",
        "domain": "procurement",
        "supported_query": "Which review is required before a purchase order is issued?",
        "supported_evidence": "A purchase order requires budget owner approval before it is issued.",
        "supported_answer": "The budget owner must approve the purchase order first.",
        "contradicted_query": "Can a buyer split an order to avoid the approval threshold?",
        "contradicted_evidence": "Buyers must not split an order to avoid the approval threshold.",
        "contradicted_answer": "No, splitting an order to avoid approval is prohibited.",
        "insufficient_query": "What supplier diversity target applies to strategic purchases?",
        "partial_query": "What approval and supplier diversity rules apply to purchase orders?",
        "partial_evidence": "A purchase order requires budget owner approval before it is issued.",
        "distractors": [
            "Competitive bids are stored in the sourcing workspace.",
            "Supplier onboarding includes a tax and sanctions screening.",
            "Purchase orders are matched to invoices during payment review.",
        ],
    },
    {
        "id": "business_continuity",
        "domain": "business_continuity",
        "supported_query": "How often must a critical service recovery plan be tested?",
        "supported_evidence": "Critical service recovery plans must be tested at least annually.",
        "supported_answer": "The recovery plan must be tested at least once a year.",
        "contradicted_query": "May a service owner skip the annual recovery exercise without a risk acceptance?",
        "contradicted_evidence": "Service owners must not skip the annual recovery exercise without documented risk acceptance.",
        "contradicted_answer": "No, skipping it requires documented risk acceptance.",
        "insufficient_query": "What recovery time objective applies to a tier three service?",
        "partial_query": "What testing and recovery-time rules apply to critical services?",
        "partial_evidence": "Critical service recovery plans must be tested at least annually.",
        "distractors": [
            "Continuity exercises record participant attendance and findings.",
            "Service dependencies are reviewed during resilience planning.",
            "Major exercise findings receive an accountable remediation owner.",
        ],
    },
    {
        "id": "legal_hold",
        "domain": "legal_operations",
        "supported_query": "Who releases a legal hold after the matter is closed?",
        "supported_evidence": "The legal matter owner releases a legal hold after confirming the matter is closed.",
        "supported_answer": "The legal matter owner releases the hold after confirmation.",
        "contradicted_query": "Can a records custodian release a legal hold without legal approval?",
        "contradicted_evidence": "Records custodians must not release a legal hold without legal approval.",
        "contradicted_answer": "No, legal approval is required before release.",
        "insufficient_query": "How long must a released legal hold notice be archived?",
        "partial_query": "What release and archive rules apply to legal holds?",
        "partial_evidence": "The legal matter owner releases a legal hold after confirming the matter is closed.",
        "distractors": [
            "Custodian acknowledgements are tracked in the matter workspace.",
            "Legal holds identify custodians and relevant information sources.",
            "Matter closure notes are retained with the legal case record.",
        ],
    },
    {
        "id": "change_management",
        "domain": "it_service_management",
        "supported_query": "What approval is required for a production change?",
        "supported_evidence": "A production change requires approval from the change advisory owner before implementation.",
        "supported_answer": "The change advisory owner must approve it before implementation.",
        "contradicted_query": "May an engineer implement a normal production change without a rollback plan?",
        "contradicted_evidence": "Engineers must not implement a normal production change without a rollback plan.",
        "contradicted_answer": "No, a rollback plan is required.",
        "insufficient_query": "What outage duration qualifies for an emergency change?",
        "partial_query": "What approval and rollback rules apply to production changes?",
        "partial_evidence": "A production change requires approval from the change advisory owner before implementation.",
        "distractors": [
            "Change records include implementation and validation timestamps.",
            "Emergency changes are reviewed after service restoration.",
            "The release manager coordinates deployment windows.",
        ],
    },
    {
        "id": "software_release",
        "domain": "software_engineering",
        "supported_query": "Which evidence is required before a release is marked ready?",
        "supported_evidence": "A release requires passing automated tests and an approved release checklist before it is marked ready.",
        "supported_answer": "Passing tests and an approved release checklist are required.",
        "contradicted_query": "Can a release manager ship a release with a failed blocking test?",
        "contradicted_evidence": "Release managers must not ship a release with a failed blocking test.",
        "contradicted_answer": "No, a failed blocking test prevents shipment.",
        "insufficient_query": "What code coverage target applies to a regulated service?",
        "partial_query": "What test and coverage rules apply before a software release?",
        "partial_evidence": "A release requires passing automated tests and an approved release checklist before it is marked ready.",
        "distractors": [
            "Release notes summarize user-visible changes.",
            "Deployment manifests are versioned with the release candidate.",
            "Rollback verification is recorded after a production deployment.",
        ],
    },
    {
        "id": "records_access",
        "domain": "records_management",
        "supported_query": "Who approves access to restricted records?",
        "supported_evidence": "Access to restricted records requires approval from the records owner.",
        "supported_answer": "The records owner approves access.",
        "contradicted_query": "May a team member grant themselves access to restricted records?",
        "contradicted_evidence": "Team members must not grant themselves access to restricted records.",
        "contradicted_answer": "No, self-granted access is prohibited.",
        "insufficient_query": "How long does restricted-record access remain valid?",
        "partial_query": "What approval and access-duration rules apply to restricted records?",
        "partial_evidence": "Access to restricted records requires approval from the records owner.",
        "distractors": [
            "Access requests include a business justification.",
            "Periodic access reviews identify inactive permissions.",
            "Records owners receive notifications for access changes.",
        ],
    },
    {
        "id": "model_governance",
        "domain": "ai_governance",
        "supported_query": "What review is required before a high-impact model is deployed?",
        "supported_evidence": "A high-impact model requires documented risk review before deployment.",
        "supported_answer": "A documented risk review is required before deployment.",
        "contradicted_query": "Can a team deploy a high-impact model without recording its intended use?",
        "contradicted_evidence": "Teams must not deploy a high-impact model without recording its intended use.",
        "contradicted_answer": "No, the intended use must be recorded.",
        "insufficient_query": "What monitoring frequency applies to a high-impact model?",
        "partial_query": "What review and monitoring rules apply to high-impact models?",
        "partial_evidence": "A high-impact model requires documented risk review before deployment.",
        "distractors": [
            "Model cards record limitations and known failure modes.",
            "Evaluation datasets are versioned with the model release.",
            "Model incidents are escalated to the AI governance owner.",
        ],
    },
    {
        "id": "data_residency",
        "domain": "privacy",
        "supported_query": "Where must regulated customer data be processed?",
        "supported_evidence": "Regulated customer data must be processed in an approved regional environment.",
        "supported_answer": "It must be processed in an approved regional environment.",
        "contradicted_query": "May an engineer copy regulated customer data to an unapproved region for testing?",
        "contradicted_evidence": "Engineers must not copy regulated customer data to an unapproved region for testing.",
        "contradicted_answer": "No, copying it to an unapproved region is prohibited.",
        "insufficient_query": "What transfer mechanism is required for cross-border support?",
        "partial_query": "What processing and transfer rules apply to regulated customer data?",
        "partial_evidence": "Regulated customer data must be processed in an approved regional environment.",
        "distractors": [
            "Regional access requests are reviewed by privacy operations.",
            "Test datasets should use masked or synthetic values.",
            "Data transfer decisions are recorded in the privacy register.",
        ],
    },
    {
        "id": "customer_identity",
        "domain": "customer_support",
        "supported_query": "What verification is required before changing a customer email?",
        "supported_evidence": "A customer email change requires identity verification through the approved support flow.",
        "supported_answer": "The approved support flow must verify identity first.",
        "contradicted_query": "Can an agent change a customer email based only on an unverified request?",
        "contradicted_evidence": "Agents must not change a customer email based only on an unverified request.",
        "contradicted_answer": "No, the request must be verified.",
        "insufficient_query": "What evidence is required for a business account ownership transfer?",
        "partial_query": "What verification and ownership-transfer rules apply to customer accounts?",
        "partial_evidence": "A customer email change requires identity verification through the approved support flow.",
        "distractors": [
            "Support agents record the reason for profile changes.",
            "Account recovery cases are linked to the customer profile.",
            "High-risk changes may require a second review.",
        ],
    },
    {
        "id": "knowledge_base",
        "domain": "knowledge_management",
        "supported_query": "Who approves a policy article before publication?",
        "supported_evidence": "A policy article requires approval from the designated content owner before publication.",
        "supported_answer": "The designated content owner approves the article.",
        "contradicted_query": "May an author publish an unreviewed policy article as authoritative guidance?",
        "contradicted_evidence": "Authors must not publish an unreviewed policy article as authoritative guidance.",
        "contradicted_answer": "No, the article must be reviewed first.",
        "insufficient_query": "How often must a policy article be recertified?",
        "partial_query": "What approval and recertification rules apply to policy articles?",
        "partial_evidence": "A policy article requires approval from the designated content owner before publication.",
        "distractors": [
            "Articles include an owner and review date in their metadata.",
            "Obsolete articles are redirected to the current source of truth.",
            "Search feedback is reviewed during knowledge maintenance.",
        ],
    },
    {
        "id": "workplace_safety",
        "domain": "workplace_operations",
        "supported_query": "What must be completed before a visitor enters a restricted work area?",
        "supported_evidence": "A visitor must complete the safety briefing before entering a restricted work area.",
        "supported_answer": "The visitor must complete the safety briefing first.",
        "contradicted_query": "Can a host escort a visitor into a restricted work area without registering them?",
        "contradicted_evidence": "Hosts must not escort a visitor into a restricted work area without registration.",
        "contradicted_answer": "No, the visitor must be registered.",
        "insufficient_query": "What badge expiration period applies to temporary visitors?",
        "partial_query": "What briefing and badge rules apply to visitors in restricted areas?",
        "partial_evidence": "A visitor must complete the safety briefing before entering a restricted work area.",
        "distractors": [
            "Hosts remain responsible for visitors during the visit.",
            "Visitor logs are retained by the workplace operations team.",
            "Restricted areas display entry requirements at access points.",
        ],
    },
]


def _document(document_id: str, text: str, domain: str) -> Dict[str, Any]:
    return {
        "document_id": document_id,
        "text": text,
        "metadata": {
            "domain": domain,
            "source_type": "template_generated_policy",
            "privacy_status": "synthetic_no_personal_data",
        },
    }


def _case(scenario: Dict[str, Any], case_type: str, sequence: int) -> Dict[str, Any]:
    prefix = f"enterprise-{scenario['id']}-{sequence:03d}"
    distractors = scenario["distractors"]
    if case_type == "supported":
        query = scenario["supported_query"]
        evidence = scenario["supported_evidence"]
        answer = scenario["supported_answer"]
        decision = "TRUE"
        relevant_index = 0
        candidate_indexes = [0, 1, 2]
    elif case_type == "contradicted":
        query = scenario["contradicted_query"]
        evidence = scenario["contradicted_evidence"]
        answer = scenario["contradicted_answer"]
        decision = "FALSE"
        relevant_index = 0
        candidate_indexes = [0, 0, 1]
    elif case_type == "insufficient":
        query = scenario["insufficient_query"]
        evidence = None
        answer = "The requested policy detail is not present in the supplied context."
        decision = "UNDECIDABLE"
        relevant_index = None
        candidate_indexes = [1, 2]
    elif case_type == "partial":
        query = scenario["partial_query"]
        evidence = scenario["partial_evidence"]
        answer = "Only one of the requested policy scopes is supported by the supplied context."
        decision = "UNDECIDABLE"
        relevant_index = 0
        candidate_indexes = [0, 1]
    else:
        raise ValueError(f"unknown case type: {case_type}")

    texts = [evidence, *distractors] if evidence else [*distractors]
    documents = [_document(f"{prefix}-doc-{index}", text, scenario["domain"]) for index, text in enumerate(texts)]
    relevant_ids = [documents[relevant_index]["document_id"]] if relevant_index is not None else []
    candidate_ids = [documents[index]["document_id"] for index in candidate_indexes]
    return {
        "case_id": f"{prefix}-{case_type}",
        "query": query,
        "documents": documents,
        "metadata": {
            "domain": scenario["domain"],
            "scenario_family": scenario["id"],
            "case_type": case_type,
            "source_type": "template_generated_enterprise_policy",
            "privacy_status": "synthetic_no_personal_data",
            "review_status": "not_production_data",
        },
        "relevant_document_ids": relevant_ids,
        "retrieved_document_ids": candidate_ids,
        "answer": answer,
        "expected_decision": decision,
    }


def generate(output_dir: str | Path) -> Path:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    cases = []
    sequence = 1
    for scenario in SCENARIOS:
        for case_type in ("supported", "contradicted", "insufficient", "partial"):
            cases.append(_case(scenario, case_type, sequence))
            sequence += 1
    cases_path = target / "cases.jsonl"
    with cases_path.open("w", encoding="utf-8") as handle:
        for case in cases:
            handle.write(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n")
    manifest = {
        "schema_version": "quimera_rag_evaluation_manifest_v2",
        "package_id": "quimera_rag_enterprise_anonymized",
        "version": "2026-08-20-v1",
        "path": "data/evaluation/rag_enterprise_v1/cases.jsonl",
        "sample_count": len(cases),
        "scenario_family_count": len(SCENARIOS),
        "case_type_counts": {case_type: len(SCENARIOS) for case_type in ("supported", "contradicted", "insufficient", "partial")},
        "provenance": {
            "source_type": "template_generated_semisynthetic",
            "contains_production_records": False,
            "contains_personal_data": False,
            "anonymization_status": "synthetic_identifiers_only",
            "review_status": "not_a_real_customer_dataset",
        },
        "limitations": [
            "Cases are semisynthetic enterprise-policy scenarios, not extracted customer records.",
            "The four case patterns are balanced by construction.",
            "Threshold curves estimate behavior on this corpus and do not establish production quality.",
        ],
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return cases_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(Path(__file__).parent))
    args = parser.parse_args()
    print(generate(args.output_dir))
