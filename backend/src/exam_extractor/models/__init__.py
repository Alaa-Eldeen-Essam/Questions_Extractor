"""Domain contracts used by every pipeline stage."""

from .artifacts import ArtifactKind, ArtifactRef
from .frames import FrameEvidence, OCRResult
from .jobs import Job, JobStatus, StageName, StageResult, StageStatus
from .questions import AnswerOption, EvidenceRef, QuestionRecord
from .sources import AcquiredSource, SourceKind, SourceMetadata, SourceRef
from .transcripts import Transcript, TranscriptSegment

__all__ = [
    "AcquiredSource",
    "AnswerOption",
    "ArtifactKind",
    "ArtifactRef",
    "EvidenceRef",
    "FrameEvidence",
    "Job",
    "JobStatus",
    "OCRResult",
    "QuestionRecord",
    "SourceKind",
    "SourceMetadata",
    "SourceRef",
    "StageName",
    "StageResult",
    "StageStatus",
    "Transcript",
    "TranscriptSegment",
]
