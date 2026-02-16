"""
Unified Docling Parser.
Returns native DoclingDocument objects, replacing custom IR.
"""

from pathlib import Path

from docling.datamodel.base_models import InputFormat
from docling.datamodel.document import DoclingDocument
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableStructureOptions
from docling.document_converter import DocumentConverter, PdfFormatOption


class DoclingParser:
    def __init__(self):
        # config
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        pipeline_options.do_table_structure = True
        pipeline_options.table_structure_options = TableStructureOptions(
            do_cell_matching=True
        )
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

    def parse(self, file_path: Path) -> DoclingDocument:
        conversion_result = self.converter.convert(file_path)
        return conversion_result.document
