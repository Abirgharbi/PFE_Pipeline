"""Package marker for `pipeline.delivery`.

This package implements the delivery stage of the STM32Cube preprocessing
pipeline: it exports the final "ST-ready" JSON artifacts (issues, files,
resolver cases, diagnostic cards) from the cleaned/enriched/linked datasets
under `data/` into `datasets/07_delivery/st_ready/`, ready for upload to the
ST AI Bridge knowledge base via `pipeline_Automation/upload/Add_Data_Source_Files.py`.

See `pipeline/delivery/README.md` for an overview of every script in this
package, its inputs/outputs, and how to run it.
"""
