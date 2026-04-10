from sqlalchemy.orm import Session

from app.models.patent import Patent
from app.models.invention_disclosure import InventionDisclosure
from app.models.research_report import ResearchReport
from app.models.inventor_qa import InventorQA
from app.schemas.patent import PatentCreate


def list_patents(db: Session) -> list[Patent]:
    return db.query(Patent).order_by(Patent.created_at.desc()).all()


def get_patent(db: Session, patent_id: int) -> Patent | None:
    return db.query(Patent).filter(Patent.patent_id == patent_id).first()


def create_patent(db: Session, data: PatentCreate) -> Patent:
    """
    Creates a patent record and any selected document records in one transaction.
    The home page creation flow collects patent metadata plus optional document
    sections (invention disclosure, research report, inventor Q&A). All records
    are created together so a partial failure doesn't leave orphaned data.
    """
    patent = Patent(
        patent_name=data.patent_name,
        patent_owner=data.patent_owner,
    )
    db.add(patent)
    # Flush to get patent_id before creating child records
    db.flush()

    if data.invention_disclosure:
        db.add(InventionDisclosure(
            patent_id=patent.patent_id,
            prior_art_and_problems=data.invention_disclosure.prior_art_and_problems,
            closest_prior_patents=data.invention_disclosure.closest_prior_patents,
            novel_features=data.invention_disclosure.novel_features,
        ))

    if data.research_report:
        db.add(ResearchReport(
            patent_id=patent.patent_id,
            executive_summary=data.research_report.executive_summary,
            search_strategy=data.research_report.search_strategy,
            classification_and_keywords=data.research_report.classification_and_keywords,
            element_patent_analysis=data.research_report.element_patent_analysis,
        ))

    if data.inventor_qna:
        db.add(InventorQA(
            patent_id=patent.patent_id,
            questions_and_answers=data.inventor_qna.questions_and_answers,
        ))

    db.commit()
    db.refresh(patent)
    return patent


def delete_patent(db: Session, patent_id: int) -> bool:
    patent = get_patent(db, patent_id)
    if not patent:
        return False
    db.delete(patent)
    db.commit()
    return True
