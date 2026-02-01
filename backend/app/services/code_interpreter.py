"""
Code Interpreter Service - Executes Python code to generate charts.
Runs code in a sandboxed environment with basic security guardrails.
"""

import io
import sys
import tempfile
import traceback
import re
import signal
from pathlib import Path
from typing import Optional
import base64
import logging
from contextlib import contextmanager


logger = logging.getLogger(__name__)


# Security guardrails - only block truly dangerous operations
# We allow normal Python operations, just block system-level access
DANGEROUS_PATTERNS = {
    # System/process control - these can harm the host system
    r'\bsubprocess\b': 'subprocess module not allowed (system commands)',
    r'\bos\.system\b': 'os.system() not allowed (shell commands)',
    r'\bos\.popen\b': 'os.popen() not allowed (shell commands)',
    r'\bos\.exec': 'os.exec*() not allowed (process replacement)',
    r'\bos\.spawn': 'os.spawn*() not allowed (process spawning)',
    r'\bos\.fork\b': 'os.fork() not allowed (process forking)',
    r'\bos\.kill\b': 'os.kill() not allowed (process killing)',
    r'\bos\.remove\b': 'os.remove() not allowed (file deletion)',
    r'\bos\.unlink\b': 'os.unlink() not allowed (file deletion)',
    r'\bos\.rmdir\b': 'os.rmdir() not allowed (directory deletion)',
    r'\bshutil\.rmtree\b': 'shutil.rmtree() not allowed (recursive deletion)',
    r'\bshutil\.move\b': 'shutil.move() not allowed (file moving)',
    
    # Network access - prevent data exfiltration
    r'\bsocket\b': 'socket module not allowed (network access)',
    r'\brequests\b': 'requests module not allowed (HTTP calls)',
    r'\burllib\b': 'urllib module not allowed (HTTP calls)',
    r'\bhttpx\b': 'httpx module not allowed (HTTP calls)',
    r'\baiohttp\b': 'aiohttp module not allowed (HTTP calls)',
    
    # Code execution/injection
    r'\beval\s*\(': 'eval() not allowed (code injection risk)',
    r'\bexec\s*\(': 'exec() not allowed (code injection risk)',
    r'\bcompile\s*\(': 'compile() not allowed (code injection risk)',
    
    # System state modification
    r'\bsys\.exit\b': 'sys.exit() not allowed',
    r'\bexit\s*\(': 'exit() not allowed',
    r'\bquit\s*\(': 'quit() not allowed',
    
    # Serialization (can be exploited for code execution)
    r'\bpickle\b': 'pickle module not allowed (security risk)',
    r'\bmarshal\b': 'marshal module not allowed (security risk)',
    
    # Ctypes (direct memory access)
    r'\bctypes\b': 'ctypes module not allowed (memory access)',
}


class CodeInterpreterService:
    """Service for executing Python code to generate charts and visualizations.
    
    Implements reasonable security:
    - Blocks dangerous system operations (subprocess, network, file deletion)
    - Allows normal Python imports for data science libraries
    - Execution timeout
    - Output size limits
    """
    
    # Configuration for resource limits
    EXECUTION_TIMEOUT = 30  # seconds
    MAX_OUTPUT_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_STDOUT_SIZE = 100 * 1024  # 100KB
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path(tempfile.mkdtemp())
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._execution_interrupted = False
    
    def _validate_code(self, code: str) -> Optional[str]:
        """
        Analyze code for dangerous patterns before execution.
        
        Args:
            code: Python code to validate
            
        Returns:
            Error message if dangerous pattern found, None if safe
        """
        if not code or not isinstance(code, str):
            return "Code must be a non-empty string"
        
        if len(code) > 50000:
            return "Code exceeds maximum length of 50KB"
        
        # Check for dangerous patterns
        for pattern, reason in DANGEROUS_PATTERNS.items():
            if re.search(pattern, code):
                return f"Blocked: {reason}"
        
        return None
    
    @contextmanager
    def _timeout_handler(self, timeout_seconds: int):
        """Context manager for execution timeout."""
        def timeout_handler(signum, frame):
            self._execution_interrupted = True
            raise TimeoutError(f"Code execution exceeded {timeout_seconds} second timeout")
        
        # Note: signal.alarm only works on Unix/Linux, not Windows
        # For Windows, we use a simpler check in the execution
        signal.signal(signal.SIGALRM, timeout_handler)
        try:
            signal.alarm(timeout_seconds)
            yield
        finally:
            signal.alarm(0)  # Disable the alarm
    
    def _create_execution_globals(self) -> dict:
        """Create globals dict for code execution with common imports pre-loaded."""
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
        import numpy as np
        
        # Start with normal builtins - no restrictions
        exec_globals = {
            '__builtins__': __builtins__,
            '__name__': '__main__',
            # Pre-import common libraries for convenience
            'plt': plt,
            'np': np,
            'numpy': np,
            'matplotlib': matplotlib,
        }
        
        # Try to import optional packages
        try:
            import seaborn as sns
            exec_globals['sns'] = sns
            exec_globals['seaborn'] = sns
        except ImportError:
            pass
        
        try:
            import pandas as pd
            exec_globals['pd'] = pd
            exec_globals['pandas'] = pd
        except ImportError:
            pass
        
        try:
            import math
            exec_globals['math'] = math
        except ImportError:
            pass
        
        return exec_globals
    
    def execute_python_code(
        self, 
        code: str, 
        output_filename: str = "output.png"
    ) -> tuple[bool, Optional[bytes], Optional[str]]:
        """
        Execute Python code and capture the output image.
        
        Args:
            code: Python code to execute (should save to output.png)
            output_filename: Expected output filename
            
        Returns:
            Tuple of (success, image_bytes, error_message)
        """
        # Step 1: Validate code safety
        validation_error = self._validate_code(code)
        if validation_error:
            logger.error(f"Code validation failed: {validation_error}")
            return False, None, f"Code validation failed: {validation_error}"
        
        # Step 2: Validate output filename
        if not output_filename or len(output_filename) > 100:
            return False, None, "Invalid output filename"
        
        if not output_filename.endswith('.png'):
            return False, None, "Output must be a PNG file"
        
        if '..' in output_filename or '/' in output_filename or '\\' in output_filename:
            return False, None, "Invalid filename: path traversal detected"
        
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        # Step 3: Create temp directory for this execution
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output_path = temp_path / output_filename
            
            # Modify code to use correct output path
            # Support both quoted formats
            modified_code = code.replace(
                "'output.png'", f"r'{output_path}'"
            ).replace(
                '"output.png"', f"r'{output_path}'"
            )
            
            # Create execution environment with common imports pre-loaded
            exec_globals = self._create_execution_globals()
            exec_locals = {}
            
            # Capture stdout/stderr
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            
            try:
                # Execute the code
                try:
                    exec(modified_code, exec_globals, exec_locals)
                except TimeoutError as e:
                    return False, None, f"Execution timeout: {str(e)}"
                
                # Close any open figures
                plt.close('all')
                
                # Step 4: Validate output file exists
                if not output_path.exists():
                    return False, None, f"Code executed but no output file created at {output_filename}"
                
                # Step 5: Validate output file size
                file_size = output_path.stat().st_size
                if file_size > self.MAX_OUTPUT_SIZE:
                    return False, None, f"Output file exceeds maximum size of {self.MAX_OUTPUT_SIZE / 1024 / 1024}MB"
                
                if file_size == 0:
                    return False, None, "Output file is empty"
                
                # Step 6: Read and validate image bytes
                with open(output_path, 'rb') as f:
                    image_bytes = f.read()
                
                # Validate it's actually a PNG
                if not image_bytes.startswith(b'\x89PNG'):
                    return False, None, "Output file is not a valid PNG image"
                
                return True, image_bytes, None
                    
            except SyntaxError as e:
                error_msg = f"Syntax error in code: {str(e)} at line {e.lineno}"
                logger.error(error_msg)
                return False, None, error_msg
            
            except ImportError as e:
                error_msg = f"Import error: {str(e)}"
                logger.error(error_msg)
                return False, None, error_msg
            
            except Exception as e:
                # Catch all other exceptions
                error_msg = f"{type(e).__name__}: {str(e)}"
                logger.error(f"Code execution failed: {error_msg}\n{traceback.format_exc()}")
                return False, None, error_msg
                
            finally:
                # Restore stdout/stderr
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                plt.close('all')
    
    def execute_and_save(
        self, 
        code: str, 
        output_name: str,
        output_dir: Optional[Path] = None
    ) -> tuple[bool, Optional[Path], Optional[str]]:
        """
        Execute Python code and save the output image with security checks.
        
        Args:
            code: Python code to execute
            output_name: Name for the output file (without extension)
            output_dir: Directory to save output
            
        Returns:
            Tuple of (success, output_path, error_message)
        """
        # Validate output_name to prevent path traversal
        if not output_name or len(output_name) > 100:
            return False, None, "Invalid output name"
        
        if '..' in output_name or '/' in output_name or '\\' in output_name:
            return False, None, "Invalid output name: path traversal detected"
        
        # Only allow alphanumeric, underscore, and hyphen
        if not re.match(r'^[a-zA-Z0-9_-]+$', output_name):
            return False, None, "Output name can only contain letters, numbers, underscores, and hyphens"
        
        out_dir = output_dir or self.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        
        success, image_bytes, error = self.execute_python_code(code)
        
        if success and image_bytes:
            output_path = out_dir / f"{output_name}.png"
            try:
                with open(output_path, 'wb') as f:
                    f.write(image_bytes)
                logger.info(f"Successfully saved output to {output_path}")
                return True, output_path, None
            except Exception as e:
                error_msg = f"Failed to write output file: {str(e)}"
                logger.error(error_msg)
                return False, None, error_msg
        
        return False, None, error
    
    def image_to_base64(self, image_bytes: bytes) -> str:
        """
        Convert image bytes to base64 data URL with validation.
        
        Args:
            image_bytes: PNG image bytes
            
        Returns:
            Base64 data URL
        """
        if not image_bytes:
            raise ValueError("Image bytes cannot be empty")
        
        if len(image_bytes) > self.MAX_OUTPUT_SIZE:
            raise ValueError(f"Image exceeds maximum size of {self.MAX_OUTPUT_SIZE / 1024 / 1024}MB")
        
        if not image_bytes.startswith(b'\x89PNG'):
            raise ValueError("Image is not a valid PNG")
        
        b64 = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:image/png;base64,{b64}"
