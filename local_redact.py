import logging

from presidio_analyzer import Pattern, PatternRecognizer
from presidio_anonymizer.entities import OperatorConfig

from pipeline import _get_presidio_de, _redact

log = logging.getLogger(__name__)

HIGH_TIER = {"TAX_ID", "PASSWORD"}
MODERATE_TIER = {"IBAN_CODE", "PHONE_NUMBER"}

EXTRA_RECOGNIZERS = [
    PatternRecognizer(
        supported_entity="PASSWORD",
        patterns=[Pattern(
            "pin_no_colon",
            r"\b(?:PIN(?:-Code)?|Geheimzahl|TAN|Zugangscode)\b\s*[:=]?\s*\d{4,8}\b",
            0.85)],
        supported_language="de",
    ),
]
_extras_added = False


def get_analyzer():
    """Shared Presidio engine plus the extra recognizers (added once)."""
    global _extras_added
    analyzer, anonymizer = _get_presidio_de()
    if not _extras_added:
        for rec in EXTRA_RECOGNIZERS:
            analyzer.registry.add_recognizer(rec)
        _extras_added = True
    return analyzer, anonymizer


def redact_de(text: str | None) -> str | None:
    """Two-tier German redaction: full mask for high tier, partial for moderate."""
    if text is None:
        return None
    try:
        analyzer, anonymizer = get_analyzer()
        results = analyzer.analyze(text=text, language="de",
                                   entities=sorted(HIGH_TIER | MODERATE_TIER))
        operators = {
            e: OperatorConfig("replace", {"new_value": f"[{e}]"}) for e in HIGH_TIER
        }
        operators.update({
            e: OperatorConfig("custom", {"lambda": lambda x, et=e: _redact(et, x)})
            for e in MODERATE_TIER
        })
        found = sorted({r.entity_type for r in results})
        log.info(f"  Redacted {len(results)} item(s): {found}" if results
                 else "  No PII entities found")
        return anonymizer.anonymize(text=text, analyzer_results=results,
                                    operators=operators).text
    except Exception as e:
        log.warning(f"Redaction failed ({type(e).__name__}) - withholding text")
        return None
