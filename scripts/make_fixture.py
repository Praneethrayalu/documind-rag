"""Author a small synthetic operational handbook and 50 grounded QA pairs.

No private data, scraped material, or claimed real-company policies.
"""
import json
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
# Each page is a distinct synthetic policy topic. Values are intentionally explicit.
TOPICS = [
    ("Incident response", [
        ("Critical incidents must be acknowledged within fifteen minutes.", "How quickly must a critical incident be acknowledged?", "fifteen minutes"),
        ("The incident commander owns the response timeline.", "Who owns the incident response timeline?", "incident commander"),
        ("Security incidents are escalated to the security duty officer.", "Who receives escalated security incidents?", "security duty officer"),
        ("A post-incident review is due within five business days.", "When is the post-incident review due?", "five business days"),
        ("Customer status updates are sent every thirty minutes during an outage.", "How often are customers updated during an outage?", "thirty minutes")]),
    ("Access control", [
        ("Production access requires approval from a service owner.", "Who must approve access to production?", "service owner"),
        ("Privileged access expires after eight hours.", "How long does privileged access last?", "eight hours"),
        ("All administrator accounts require a hardware security key.", "What security device is required for administrator accounts?", "hardware security key"),
        ("User access is reviewed every calendar quarter.", "How often is user access reviewed?", "calendar quarter"),
        ("Departed employee access must be removed within one hour.", "How fast must access for a departed employee be removed?", "one hour")]),
    ("Backups", [
        ("Database backups run daily at 02:00 UTC.", "At what time do database backups run?", "02:00 UTC"),
        ("Daily backup retention is thirty days.", "How long are daily backups retained?", "thirty days"),
        ("Backup restoration drills happen every month.", "How frequently are backup restoration drills held?", "every month"),
        ("The recovery point objective is twenty-four hours.", "What is the recovery point objective?", "twenty-four hours"),
        ("The recovery time objective is four hours.", "What is the recovery time objective?", "four hours")]),
    ("Data handling", [
        ("Confidential documents must be encrypted at rest with AES-256.", "Which encryption protects confidential documents at rest?", "AES-256"),
        ("Customer export links expire after forty-eight hours.", "When do customer export links expire?", "forty-eight hours"),
        ("Personal data deletion requests are completed within thirty calendar days.", "What is the deadline for personal data deletion requests?", "thirty calendar days"),
        ("Restricted data may only be stored in the approved regional vault.", "Where can restricted data be stored?", "approved regional vault"),
        ("The privacy lead approves new personal data processing purposes.", "Who approves a new purpose for processing personal data?", "privacy lead")]),
    ("Release management", [
        ("Normal releases are scheduled on Tuesdays at 10:00 UTC.", "When are normal releases scheduled?", "Tuesdays at 10:00 UTC"),
        ("Every production release needs two peer approvals.", "How many peer approvals are needed for a production release?", "two peer approvals"),
        ("Canary deployments initially serve five percent of traffic.", "What traffic share does an initial canary deployment receive?", "five percent"),
        ("A release is rolled back when the error rate exceeds two percent.", "What error rate triggers a release rollback?", "two percent"),
        ("Emergency releases require approval from the engineering duty manager.", "Who approves emergency releases?", "engineering duty manager")]),
    ("Support", [
        ("The standard support desk operates from 08:00 to 18:00 UTC.", "What are the standard support desk hours?", "08:00 to 18:00 UTC"),
        ("Priority one support tickets have a response target of ten minutes.", "What is the response target for priority one support tickets?", "ten minutes"),
        ("Priority two tickets have a response target of two hours.", "What is the response target for priority two tickets?", "two hours"),
        ("Support ticket attachments are deleted after ninety days.", "How long are support ticket attachments kept?", "ninety days"),
        ("The support lead reviews unresolved tickets every morning.", "Who reviews unresolved tickets each morning?", "support lead")]),
    ("Equipment", [
        ("Company laptops are replaced every four years.", "How often are company laptops replaced?", "four years"),
        ("Lost equipment must be reported within two hours of discovery.", "When must lost equipment be reported?", "two hours"),
        ("Full disk encryption is mandatory on every company laptop.", "What encryption requirement applies to company laptops?", "Full disk encryption"),
        ("Equipment returns are handled by the workplace operations team.", "Which team handles equipment returns?", "workplace operations team"),
        ("Laptop operating system updates are installed within seven days.", "What is the deadline for laptop operating system updates?", "seven days")]),
    ("Vendor review", [
        ("Vendors handling customer data receive a security review annually.", "How often are vendors handling customer data reviewed?", "annually"),
        ("The procurement lead owns the vendor inventory.", "Who owns the vendor inventory?", "procurement lead"),
        ("New vendor contracts require a signed data processing agreement.", "What signed agreement is required for a new vendor contract?", "data processing agreement"),
        ("High risk vendor findings must be remediated within fourteen days.", "How quickly must high risk vendor findings be remediated?", "fourteen days"),
        ("Vendor offboarding includes deleting integration credentials.", "What happens to integration credentials during vendor offboarding?", "deleting integration credentials")]),
    ("Service reliability", [
        ("The monthly service availability target is 99.9 percent.", "What is the monthly service availability target?", "99.9 percent"),
        ("Health probes run every sixty seconds.", "How often do health probes run?", "sixty seconds"),
        ("Capacity forecasts are reviewed on the first Monday of each month.", "When are capacity forecasts reviewed?", "first Monday"),
        ("Application error logs are retained for twenty-one days.", "How long are application error logs retained?", "twenty-one days"),
        ("On-call rotations change every Wednesday at 09:00 UTC.", "When do on-call rotations change?", "Wednesday at 09:00 UTC")]),
    ("Travel and expenses", [
        ("Expense claims must be filed within twenty days of travel.", "When must expense claims be filed?", "twenty days"),
        ("International travel requires director approval.", "Who approves international travel?", "director approval"),
        ("Economy class is the default for company flights.", "What is the default flight class for company travel?", "Economy class"),
        ("Itemized receipts are required for meal reimbursement.", "What receipts are required for meal reimbursement?", "Itemized receipts"),
        ("The finance team pays approved expenses every Friday.", "When are approved expenses paid?", "every Friday")]),
]


def main():
    path = ROOT / "data/sample/documind-handbook.pdf"
    pdf = canvas.Canvas(str(path), pagesize=A4, invariant=1)
    pdf.setTitle("DocuMind synthetic operational handbook")
    questions, source = [], []
    for page, (topic, facts) in enumerate(TOPICS, 1):
        pdf.setFont("Helvetica-Bold", 19)
        pdf.drawString(48, 790, topic)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(48, 768, "Synthetic test policy. Not advice or a real organization's rules.")
        y = 720
        source.append({"page": page, "topic": topic, "facts": [x[0] for x in facts]})
        for fact, question, expected in facts:
            words, line = fact.split(), ""
            for word in words:
                if len(line + word) > 88:
                    pdf.drawString(48, y, line)
                    y -= 16
                    line = ""
                line += word + " "
            pdf.drawString(48, y, line)
            y -= 42
            questions.append({"id": f"q{len(questions)+1:02}", "question": question, "reference": fact, "expected_substring": expected, "source": path.name, "expected_page": page})
        pdf.setFont("Helvetica", 9)
        pdf.drawString(48, 40, f"DocuMind evaluation fixture | Page {page}")
        pdf.showPage()
    pdf.save()
    (ROOT / "evaluation/questions.json").write_text(json.dumps(questions, indent=2) + "\n")
    (ROOT / "data/sample/handbook-source.json").write_text(json.dumps(source, indent=2) + "\n")
    print(f"Wrote {path} and {len(questions)} QA pairs")


if __name__ == "__main__":
    main()
