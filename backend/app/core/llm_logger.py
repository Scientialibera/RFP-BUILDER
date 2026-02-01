"""
LLM response logging utility.
Logs all LLM function calls and responses in a beautified, readable format.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LLMLogger:
    """Handles logging of LLM requests and responses."""
    
    def __init__(self, log_dir: Path):
        """Initialize LLM logger."""
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create session directory with timestamp
        self.session_dir = self.log_dir / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"LLM Logger initialized: {self.session_dir}")
    
    def log_step(
        self,
        step_name: str,
        function_name: str,
        function_args: dict[str, Any],
        raw_response: str,
        parsed_result: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Log a complete workflow step with LLM interaction.
        
        Args:
            step_name: Workflow step (e.g., 'analyze', 'generate', 'review')
            function_name: LLM function called (e.g., 'analyze_rfp', 'generate_rfp_response')
            function_args: Parsed function arguments
            raw_response: Raw LLM response text
            parsed_result: Parsed function result
        """
        try:
            # Create step log file
            step_file = self.session_dir / f"{step_name}_{function_name}.json"
            
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "step": step_name,
                "function": function_name,
                "function_arguments": function_args,
                "raw_response": raw_response,
                "parsed_result": parsed_result or {}
            }
            
            # Write JSON log
            with open(step_file, "w") as f:
                json.dump(log_entry, f, indent=2, default=str)
            
            # Create beautified markdown log
            md_file = step_file.with_suffix(".md")
            self._write_markdown_log(md_file, step_name, function_name, function_args, parsed_result)
            
            logger.info(f"Logged step: {step_name}/{function_name}")
            
        except Exception as e:
            logger.error(f"Failed to log step {step_name}: {str(e)}")
    
    def _write_markdown_log(
        self,
        file_path: Path,
        step_name: str,
        function_name: str,
        function_args: dict[str, Any],
        parsed_result: Optional[dict[str, Any]]
    ) -> None:
        """Write a beautified markdown log file."""
        md_lines = []
        
        # Header
        md_lines.append(f"# {step_name.upper()}: {function_name}")
        md_lines.append(f"**Time**: {datetime.now().isoformat()}")
        md_lines.append("")
        
        # Function Arguments
        md_lines.append("## Function Arguments")
        md_lines.append("")
        md_lines.extend(self._format_dict_as_markdown(function_args, level=3))
        md_lines.append("")
        
        # Parsed Result
        if parsed_result:
            md_lines.append("## Parsed Function Result")
            md_lines.append("")
            md_lines.extend(self._format_dict_as_markdown(parsed_result, level=3))
            md_lines.append("")
        
        # Write to file
        with open(file_path, "w") as f:
            f.write("\n".join(md_lines))
    
    def _format_dict_as_markdown(
        self,
        data: Any,
        level: int = 3,
        indent: int = 0
    ) -> list[str]:
        """
        Format a dictionary as markdown with proper indentation and nesting.
        
        Args:
            data: Data to format
            level: Heading level for keys (3 = ###)
            indent: Current indentation level
            
        Returns:
            List of markdown lines
        """
        lines = []
        indent_str = "  " * indent
        
        if isinstance(data, dict):
            for key, value in data.items():
                # Skip very long values
                if isinstance(value, str) and len(str(value)) > 500:
                    value = f"{str(value)[:500]}... (truncated)"
                
                if isinstance(value, dict):
                    lines.append(f"{indent_str}### {self._format_key(key)}")
                    lines.append("")
                    lines.extend(self._format_dict_as_markdown(value, level=level+1, indent=indent+1))
                    lines.append("")
                elif isinstance(value, list):
                    lines.append(f"{indent_str}### {self._format_key(key)}")
                    lines.append("")
                    for i, item in enumerate(value[:10]):  # Limit list items
                        if isinstance(item, dict):
                            lines.append(f"{indent_str}#### Item {i+1}")
                            lines.extend(self._format_dict_as_markdown(item, level=level+2, indent=indent+2))
                        else:
                            lines.append(f"{indent_str}- {self._format_value(item)}")
                    if len(value) > 10:
                        lines.append(f"{indent_str}... and {len(value)-10} more items")
                    lines.append("")
                else:
                    formatted_value = self._format_value(value)
                    lines.append(f"{indent_str}- **{self._format_key(key)}**: {formatted_value}")
        elif isinstance(data, list):
            for i, item in enumerate(data[:10]):
                lines.append(f"{indent_str}- Item {i+1}: {self._format_value(item)}")
            if len(data) > 10:
                lines.append(f"{indent_str}... and {len(data)-10} more items")
        else:
            lines.append(str(data))
        
        return lines
    
    @staticmethod
    def _format_key(key: str) -> str:
        """Format a key for display (snake_case -> Title Case)."""
        return key.replace("_", " ").title()
    
    @staticmethod
    def _format_value(value: Any) -> str:
        """Format a value for display."""
        if isinstance(value, bool):
            return "✓ Yes" if value else "✗ No"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            if len(value) > 100:
                return f"`{value[:100]}...`"
            elif value.strip().startswith("{") or value.strip().startswith("["):
                try:
                    parsed = json.loads(value)
                    return f"`{json.dumps(parsed, indent=2)}`"
                except:
                    return f"`{value}`"
            else:
                return f"`{value}`"
        else:
            return f"`{str(value)}`"
    
    def get_session_logs(self) -> list[Path]:
        """Get all log files in current session."""
        return sorted(self.session_dir.glob("*.json"))
    
    def get_session_summary(self) -> str:
        """Get a summary of all logs in current session."""
        logs = self.get_session_logs()
        summary_lines = [
            f"# LLM Logs Summary",
            f"**Session**: {self.session_dir.name}",
            f"**Logs**: {len(logs)} steps recorded",
            ""
        ]
        
        for log_file in logs:
            step_name = log_file.stem.split("_")[0]
            summary_lines.append(f"- {step_name}: {log_file.name}")
        
        return "\n".join(summary_lines)


def create_llm_logger(log_dir: str) -> LLMLogger:
    """Factory function to create an LLM logger."""
    return LLMLogger(Path(log_dir))
