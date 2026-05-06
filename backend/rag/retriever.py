"""High-level retrieval API and one-time knowledge base seeding."""

from __future__ import annotations

from dotenv import load_dotenv

from backend.rag.vector_store import VectorStore
from backend.utils.logger import get_logger

load_dotenv()
logger = get_logger(__name__)


class KnowledgeRetriever:
    """Retrieves IT support knowledge base entries for a given query."""

    def __init__(self) -> None:
        self.store = VectorStore()

    def count(self) -> int:
        return self.store.count()

    def retrieve(self, query: str, n_results: int = 3) -> str:
        """Return a human-readable string of the top-k matching entries."""
        results = self.store.query(query, n_results=n_results)
        if not results:
            return "Relevant Knowledge Base Entries:\n(no results)"

        lines = ["Relevant Knowledge Base Entries:"]
        for i, r in enumerate(results, start=1):
            lines.append(f"{i}. {r['text']}")
        return "\n".join(lines)

    def retrieve_with_scores(self, query: str, n_results: int = 3) -> list[dict]:
        """Return raw retrieval results including distances — useful for tests."""
        return self.store.query(query, n_results=n_results)


# ---------------------------------------------------------------------------
# Knowledge base seed
# ---------------------------------------------------------------------------

_SEED_DOCS: list[dict] = [
    {
        "id": "kb-001",
        "category": "password",
        "text": (
            "Password reset procedure: Go to https://portal.company.com/reset, enter your "
            "corporate email, and follow the link sent to your registered email. Reset links "
            "expire after 30 minutes. If the link expired, request a new one. Passwords must "
            "be at least 12 characters with one uppercase letter, one number, and one symbol."
        ),
    },
    {
        "id": "kb-002",
        "category": "network",
        "text": (
            "VPN setup steps: 1) Install Cisco AnyConnect from the company app catalog. "
            "2) Connect to vpn.company.com. 3) Enter your corporate username and password. "
            "4) Approve the MFA push on your phone. If the push never arrives, check that you "
            "are connected to the internet and that the Duo Mobile app is signed in."
        ),
    },
    {
        "id": "kb-003",
        "category": "software",
        "text": (
            "Software installation error 1603: This indicates a fatal error during MSI install, "
            "usually caused by a previous failed install. Resolution: open Add/Remove Programs, "
            "remove any partial install, reboot, and re-run the installer as Administrator. "
            "Check %TEMP%\\MSI*.log for the exact failing component."
        ),
    },
    {
        "id": "kb-004",
        "category": "hardware",
        "text": (
            "Printer troubleshooting: 1) Confirm the printer has paper and no jam. 2) Restart "
            "the print spooler service (services.msc → Print Spooler → Restart). 3) Remove and "
            "re-add the printer from Settings → Printers & scanners. 4) For network printers, "
            "ping the printer IP to confirm reachability."
        ),
    },
    {
        "id": "kb-005",
        "category": "access",
        "text": (
            "Account lockout resolution: Accounts lock after 5 failed login attempts and "
            "automatically unlock after 15 minutes. To unlock immediately, request unlock from "
            "the IT self-service portal or call the helpdesk. After unlock, change your password "
            "if you suspect any unauthorized attempts."
        ),
    },
    {
        "id": "kb-006",
        "category": "software",
        "text": (
            "Windows error 0x80070005 means 'Access Denied'. It typically appears during "
            "Windows Update or file operations and is caused by missing permissions or a "
            "corrupted user profile. Fix: run the troubleshooter (Settings → Update & Security "
            "→ Troubleshoot), reset Windows Update components, or run sfc /scannow."
        ),
    },
    {
        "id": "kb-007",
        "category": "network",
        "text": (
            "Network connectivity troubleshooting: 1) Check the wifi/ethernet icon. 2) Run "
            "`ipconfig /all` and confirm a valid IP and gateway. 3) Try `ping 8.8.8.8` to test "
            "external connectivity. 4) Try `nslookup company.com` to test DNS. 5) If DNS fails, "
            "run `ipconfig /flushdns` and retry."
        ),
    },
    {
        "id": "kb-008",
        "category": "hardware",
        "text": (
            "Disk space warnings: Windows shows a warning when the system drive falls below "
            "10% free. Clear space by emptying the Recycle Bin, running Disk Cleanup, removing "
            "old Windows update files, and uninstalling unused applications. For laptops with "
            "small SSDs, move the OneDrive cache and Downloads folder to an external drive."
        ),
    },
    {
        "id": "kb-009",
        "category": "access",
        "text": (
            "Multi-factor authentication (MFA) setup: 1) Install Microsoft Authenticator on "
            "your phone. 2) Visit https://aka.ms/mfasetup and sign in. 3) Add an account → "
            "Work or school → Scan QR code. 4) Approve the test push. Use the recovery codes "
            "you are shown to store somewhere safe in case you lose your phone."
        ),
    },
    {
        "id": "kb-010",
        "category": "software",
        "text": (
            "Common Outlook issues: If Outlook will not open, start it in safe mode "
            "(`outlook.exe /safe`) to rule out add-ins. For 'Cannot connect to Exchange', "
            "delete the Outlook profile in Control Panel → Mail and recreate it. For missing "
            "emails, check the Junk folder and the Search filters."
        ),
    },
    {
        "id": "kb-011",
        "category": "network",
        "text": (
            "Remote desktop connection steps: 1) Confirm the target machine has Remote Desktop "
            "enabled (System → Remote settings). 2) Connect to VPN. 3) Open mstsc.exe. "
            "4) Enter the machine name (e.g. PC-12345.corp.local). 5) Authenticate with your "
            "domain credentials. If the host is unreachable, ping it first."
        ),
    },
    {
        "id": "kb-012",
        "category": "software",
        "text": (
            "Browser cache clearing: In Chrome/Edge press Ctrl+Shift+Delete, choose 'All time', "
            "tick Cached images and files and Cookies, and click Clear data. This resolves "
            "many login loops, broken layouts, and stale single-sign-on issues."
        ),
    },
    {
        "id": "kb-013",
        "category": "software",
        "text": (
            "Microsoft Teams audio issues: 1) Open Teams → Settings → Devices and confirm the "
            "right microphone and speaker are selected. 2) Run a Test call. 3) If you cannot "
            "be heard, check Windows Privacy → Microphone and ensure Teams is allowed. "
            "4) Reinstall Teams if device list is empty."
        ),
    },
    {
        "id": "kb-014",
        "category": "software",
        "text": (
            "OneDrive sync problems: A red X on a OneDrive file means sync failed. Right-click "
            "the OneDrive icon in the system tray → Settings → Account → Unlink this PC, then "
            "sign back in to repair the sync state. Files larger than 250 GB or with reserved "
            "characters in the name will not sync."
        ),
    },
    {
        "id": "kb-015",
        "category": "hardware",
        "text": (
            "Blue Screen of Death (BSOD) guidance: Note the stop code shown on the blue screen "
            "(for example PAGE_FAULT_IN_NONPAGED_AREA). Common fixes: update or roll back "
            "device drivers, run `chkdsk /f`, and run `sfc /scannow`. If BSODs are repeated, "
            "collect the minidump from C:\\Windows\\Minidump and contact IT for analysis."
        ),
    },
    {
        "id": "kb-016",
        "category": "network",
        "text": (
            "DNS troubleshooting: If you can ping IPs but not hostnames, DNS is broken. Run "
            "`ipconfig /flushdns`, then `ipconfig /registerdns`. If still broken, set DNS to "
            "the corporate resolver (10.0.0.53) or a public one (1.1.1.1, 8.8.8.8) under "
            "adapter properties → IPv4 → Use the following DNS server addresses."
        ),
    },
]


def seed_knowledge_base() -> None:
    """Seed the IT knowledge base with ~15 docs. Idempotent — skips if already seeded."""
    retriever = KnowledgeRetriever()
    existing = retriever.count()
    if existing > 0:
        logger.info("Knowledge base already seeded (%d docs). Skipping.", existing)
        return

    docs = [
        {
            "id": d["id"],
            "text": d["text"],
            "metadata": {
                "category": d["category"],
                "source": "knowledge_base",
                "doc_id": d["id"],
            },
        }
        for d in _SEED_DOCS
    ]
    retriever.store.add_documents(docs)
    logger.info("Seeded knowledge base with %d documents", len(docs))


if __name__ == "__main__":
    seed_knowledge_base()
