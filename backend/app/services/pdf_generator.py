"""
PDF Generation Service - Creates formatted PDF documents from RFP sections.
"""

import io
from pathlib import Path
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, 
    Paragraph, 
    Spacer, 
    Image,
    Table,
    TableStyle,
    PageBreak,
    ListFlowable,
    ListItem,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

from app.core.config import get_config, PDFOutputConfig
from app.models.schemas import RFPSection


class PDFGeneratorService:
    """Service for generating formatted PDF documents."""
    
    PAGE_SIZES = {
        "letter": letter,
        "a4": A4,
    }
    
    def __init__(self, config: Optional[PDFOutputConfig] = None):
        if config is None:
            config = get_config().pdf_output
        self.config = config
        self._setup_styles()
    
    def _setup_styles(self):
        """Set up paragraph styles based on config."""
        self.styles = getSampleStyleSheet()
        
        # Custom H1 style
        self.styles.add(ParagraphStyle(
            name='CustomH1',
            parent=self.styles['Heading1'],
            fontName=self.config.font_family + '-Bold',
            fontSize=self.config.font_size_h1,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.HexColor('#1a1a1a'),
        ))
        
        # Custom H2 style
        self.styles.add(ParagraphStyle(
            name='CustomH2',
            parent=self.styles['Heading2'],
            fontName=self.config.font_family + '-Bold',
            fontSize=self.config.font_size_h2,
            spaceAfter=10,
            spaceBefore=16,
            textColor=colors.HexColor('#2a2a2a'),
        ))
        
        # Custom H3 style
        self.styles.add(ParagraphStyle(
            name='CustomH3',
            parent=self.styles['Heading3'],
            fontName=self.config.font_family + '-Bold',
            fontSize=self.config.font_size_h3,
            spaceAfter=8,
            spaceBefore=12,
            textColor=colors.HexColor('#3a3a3a'),
        ))
        
        # Custom body style
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['Normal'],
            fontName=self.config.font_family,
            fontSize=self.config.font_size_body,
            spaceAfter=8,
            spaceBefore=4,
            alignment=TA_JUSTIFY,
            leading=14,
        ))
        
        # Bullet list style
        self.styles.add(ParagraphStyle(
            name='BulletItem',
            parent=self.styles['Normal'],
            fontName=self.config.font_family,
            fontSize=self.config.font_size_body,
            leftIndent=20,
            spaceAfter=4,
        ))
    
    def _get_style(self, section_type: str) -> ParagraphStyle:
        """Get the appropriate style for a section type."""
        style_map = {
            'h1': 'CustomH1',
            'h2': 'CustomH2',
            'h3': 'CustomH3',
            'body': 'CustomBody',
        }
        style_name = style_map.get(section_type.lower(), 'CustomBody')
        return self.styles[style_name]
    
    def _process_content(self, content: str, section_type: str) -> list:
        """
        Process section content into flowable elements.
        Handles markdown-like formatting.
        """
        elements = []
        style = self._get_style(section_type)
        
        # Split by double newlines for paragraphs
        paragraphs = content.split('\n\n')
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Check for bullet lists
            if para.startswith('- ') or para.startswith('* '):
                lines = para.split('\n')
                bullet_items = []
                for line in lines:
                    line = line.strip()
                    if line.startswith('- ') or line.startswith('* '):
                        text = line[2:].strip()
                        bullet_items.append(
                            ListItem(Paragraph(text, self.styles['BulletItem']))
                        )
                if bullet_items:
                    elements.append(ListFlowable(
                        bullet_items,
                        bulletType='bullet',
                        start=None,
                    ))
            else:
                # Regular paragraph - escape HTML-like content
                safe_para = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                # Handle basic bold
                safe_para = safe_para.replace('**', '<b>', 1)
                while '**' in safe_para:
                    safe_para = safe_para.replace('**', '</b>', 1)
                    if '**' in safe_para:
                        safe_para = safe_para.replace('**', '<b>', 1)
                
                elements.append(Paragraph(safe_para, style))
        
        return elements
    
    def _add_image(self, image_path: Path, max_width: float = 6*inch) -> Optional[Image]:
        """Add an image element, scaling if necessary."""
        if not image_path.exists():
            return None
        
        img = Image(str(image_path))
        
        # Scale to fit
        if img.drawWidth > max_width:
            ratio = max_width / img.drawWidth
            img.drawWidth = max_width
            img.drawHeight = img.drawHeight * ratio
        
        return img
    
    def generate_pdf(
        self, 
        sections: list[RFPSection],
        output_path: Optional[Path] = None,
        title: str = "RFP Response",
        image_dir: Optional[Path] = None,
    ) -> bytes:
        """
        Generate a PDF document from RFP sections.
        
        Args:
            sections: List of RFPSection objects.
            output_path: Optional path to save the PDF.
            title: Document title.
            image_dir: Directory containing any referenced images.
            
        Returns:
            PDF content as bytes.
        """
        # Create buffer for PDF
        buffer = io.BytesIO()
        
        # Get page size
        page_size = self.PAGE_SIZES.get(
            self.config.page_size.lower(), 
            letter
        )
        
        # Create document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=page_size,
            topMargin=self.config.margin_top,
            bottomMargin=self.config.margin_bottom,
            leftMargin=self.config.margin_left,
            rightMargin=self.config.margin_right,
            title=title,
        )
        
        # Build content
        elements = []
        
        # Title page (optional)
        elements.append(Spacer(1, 2*inch))
        elements.append(Paragraph(title, self.styles['CustomH1']))
        elements.append(Spacer(1, inch))
        elements.append(PageBreak())
        
        # Process sections
        for section in sections:
            # Add section title if it's a header type
            if section.section_type in ('h1', 'h2', 'h3'):
                elements.append(Paragraph(
                    section.section_title,
                    self._get_style(section.section_type)
                ))
            
            # Process content
            content_elements = self._process_content(
                section.section_content, 
                'body'  # Content is always body style
            )
            elements.extend(content_elements)
            
            # Check for image references in content
            if image_dir:
                import re
                img_pattern = re.compile(r'!\[.*?\]\((.+?)\)')
                for match in img_pattern.finditer(section.section_content):
                    img_name = match.group(1)
                    img_path = image_dir / img_name
                    img_elem = self._add_image(img_path)
                    if img_elem:
                        elements.append(Spacer(1, 12))
                        elements.append(img_elem)
                        elements.append(Spacer(1, 12))
            
            elements.append(Spacer(1, 12))
        
        # Build PDF
        doc.build(elements)
        
        # Get bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        # Optionally save to file
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
        
        return pdf_bytes
