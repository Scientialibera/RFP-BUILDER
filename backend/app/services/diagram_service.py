"""
Diagram Service - Handles Mermaid diagram conversion to PNG.
"""

import re
import tempfile
from pathlib import Path
from typing import Optional
import subprocess


class DiagramService:
    """Service for converting Mermaid diagrams to PNG images."""
    
    # Regex to find mermaid code blocks
    MERMAID_PATTERN = re.compile(
        r'```mermaid\s*(?:\{[^}]*\})?\s*\n(.*?)```',
        re.DOTALL | re.IGNORECASE
    )
    
    def __init__(self):
        self._mmdc_available: Optional[bool] = None
    
    def is_available(self) -> bool:
        """Check if Mermaid CLI is available."""
        if self._mmdc_available is None:
            try:
                result = subprocess.run(
                    ["mmdc", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                self._mmdc_available = result.returncode == 0
            except (subprocess.SubprocessError, FileNotFoundError):
                self._mmdc_available = False
        
        return self._mmdc_available
    
    def extract_mermaid_blocks(self, content: str) -> list[dict]:
        """
        Extract all Mermaid diagram blocks from content.
        
        Args:
            content: Text content that may contain Mermaid blocks.
            
        Returns:
            List of dicts with 'code' and 'start'/'end' positions.
        """
        blocks = []
        for match in self.MERMAID_PATTERN.finditer(content):
            blocks.append({
                'code': match.group(1).strip(),
                'full_match': match.group(0),
                'start': match.start(),
                'end': match.end()
            })
        return blocks
    
    def convert_mermaid_to_png(
        self, 
        mermaid_code: str, 
        output_path: Optional[Path] = None,
        theme: str = "default",
        width: int = 1200,
        height: int = 800,
        background_color: str = "white"
    ) -> bytes:
        """
        Convert Mermaid diagram code to PNG image.
        
        Args:
            mermaid_code: The Mermaid diagram code.
            output_path: Optional path to save the PNG.
            theme: Mermaid theme (default, dark, forest, neutral).
            width: Output image width.
            height: Output image height.
            background_color: Background color.
            
        Returns:
            PNG image as bytes.
            
        Raises:
            RuntimeError: If conversion fails.
        """
        if not self.is_available():
            raise RuntimeError(
                "Mermaid CLI (mmdc) is not available. "
                "Install it with: npm install -g @mermaid-js/mermaid-cli"
            )
        
        with tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.mmd', 
            delete=False
        ) as mmd_file:
            mmd_file.write(mermaid_code)
            mmd_path = Path(mmd_file.name)
        
        try:
            if output_path is None:
                output_path = mmd_path.with_suffix('.png')
            
            # Run mmdc
            cmd = [
                "mmdc",
                "-i", str(mmd_path),
                "-o", str(output_path),
                "-t", theme,
                "-w", str(width),
                "-H", str(height),
                "-b", background_color
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                raise RuntimeError(
                    f"Mermaid conversion failed: {result.stderr}"
                )
            
            # Read the output
            with open(output_path, 'rb') as f:
                png_bytes = f.read()
            
            return png_bytes
            
        finally:
            # Cleanup temp files
            mmd_path.unlink(missing_ok=True)
            if output_path and output_path != mmd_path.with_suffix('.png'):
                pass  # Keep user-specified output
            else:
                Path(str(mmd_path.with_suffix('.png'))).unlink(missing_ok=True)
    
    def process_content_diagrams(
        self, 
        content: str, 
        output_dir: Path,
        base_name: str = "diagram"
    ) -> tuple[str, list[Path]]:
        """
        Process all Mermaid diagrams in content, converting to PNG.
        
        Args:
            content: Text content with Mermaid blocks.
            output_dir: Directory to save PNG files.
            base_name: Base name for output files.
            
        Returns:
            Tuple of (modified content with image refs, list of generated PNG paths)
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        blocks = self.extract_mermaid_blocks(content)
        png_paths = []
        
        # Process in reverse order to maintain string positions
        for i, block in enumerate(reversed(blocks)):
            idx = len(blocks) - 1 - i
            png_name = f"{base_name}_{idx}.png"
            png_path = output_dir / png_name
            
            try:
                png_bytes = self.convert_mermaid_to_png(
                    block['code'],
                    output_path=png_path
                )
                png_paths.insert(0, png_path)
                
                # Replace mermaid block with image reference
                replacement = f"![Diagram {idx}]({png_name})"
                content = (
                    content[:block['start']] + 
                    replacement + 
                    content[block['end']:]
                )
            except RuntimeError as e:
                # Keep original mermaid block but add error note
                error_note = f"\n<!-- Diagram conversion error: {e} -->\n"
                content = (
                    content[:block['end']] + 
                    error_note + 
                    content[block['end']:]
                )
        
        return content, png_paths
