"""Local YouTube Shorts creation pipeline."""

__all__ = ["PipelineConfig", "ShortsPipeline"]


def __getattr__(name: str):
    # Keep lightweight modules importable for testing before optional runtime
    # dependencies (yt-dlp, Whisper/PyTorch) have been installed.
    if name in __all__:
        from .pipeline import PipelineConfig, ShortsPipeline

        return {"PipelineConfig": PipelineConfig, "ShortsPipeline": ShortsPipeline}[name]
    raise AttributeError(name)
