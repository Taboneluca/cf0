"""
Enhanced streaming debugging utilities for cf0 API Gateway.
Provides comprehensive debugging for both ask and analyst modes.
"""

import time
import json
import os
from typing import Any, Dict, List, Optional, AsyncGenerator
from datetime import datetime
import inspect

class StreamingDebugger:
    """Comprehensive streaming debugger with detailed metrics"""
    
    def __init__(self, request_id: str, mode: str, model: str):
        self.request_id = request_id
        self.mode = mode
        self.model = model
        self.start_time = time.time()
        self.metrics = {
            "chunks_received": 0,
            "empty_chunks": 0,
            "content_chunks": 0,
            "tool_chunks": 0,
            "bytes_received": 0,
            "chunk_types": {},
            "extraction_methods": {},
            "timing": [],
            "errors": []
        }
        self.last_chunk_time = time.time()
        self.debug_enabled = os.getenv("DEBUG_STREAMING", "0") == "1"
        self.verbose = os.getenv("DEBUG_STREAMING_VERBOSE", "0") == "1"
        
    def analyze_chunk(self, chunk: Any) -> Dict[str, Any]:
        """Deep analysis of a chunk to extract content"""
        analysis = {
            "type": type(chunk).__name__,
            "attributes": [],
            "content": None,
            "content_length": 0,
            "extraction_method": None,
            "has_tool_calls": False,
            "is_empty": True,
            "raw_repr": str(chunk)[:200] if chunk else "None"
        }
        
        # Get all attributes
        if hasattr(chunk, '__dict__'):
            analysis["attributes"] = list(chunk.__dict__.keys())
            
        # Try multiple extraction methods
        extraction_attempts = [
            # Direct content
            ("direct_content", lambda: getattr(chunk, 'content', None)),
            # OpenAI format
            ("choices[0].delta.content", lambda: chunk.choices[0].delta.content if hasattr(chunk, 'choices') and chunk.choices and hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'content') else None),
            ("choices[0].message.content", lambda: chunk.choices[0].message.content if hasattr(chunk, 'choices') and chunk.choices and hasattr(chunk.choices[0], 'message') and hasattr(chunk.choices[0].message, 'content') else None),
            # Anthropic format
            ("delta.text", lambda: chunk.delta.text if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'text') else None),
            ("delta.content", lambda: chunk.delta.content if hasattr(chunk, 'delta') and hasattr(chunk.delta, 'content') else None),
            # Generic attributes
            ("text", lambda: getattr(chunk, 'text', None)),
            ("message", lambda: getattr(chunk, 'message', None)),
            # Nested content
            ("data.content", lambda: chunk.data.content if hasattr(chunk, 'data') and hasattr(chunk.data, 'content') else None),
            # String conversion as last resort
            ("str_conversion", lambda: str(chunk) if chunk and str(chunk).strip() and not str(chunk).startswith('<') else None),
        ]
        
        for method_name, extractor in extraction_attempts:
            try:
                content = extractor()
                if content and str(content).strip():
                    analysis["content"] = content
                    analysis["content_length"] = len(str(content))
                    analysis["extraction_method"] = method_name
                    analysis["is_empty"] = False
                    break
            except Exception as e:
                if self.verbose:
                    print(f"[{self.request_id}] ⚠️ Extraction method {method_name} failed: {e}")
                    
        # Check for tool calls
        tool_call_checks = [
            lambda: hasattr(chunk, 'tool_calls') and chunk.tool_calls,
            lambda: hasattr(chunk, 'choices') and chunk.choices and hasattr(chunk.choices[0], 'delta') and hasattr(chunk.choices[0].delta, 'tool_calls') and chunk.choices[0].delta.tool_calls,
        ]
        
        for check in tool_call_checks:
            try:
                if check():
                    analysis["has_tool_calls"] = True
                    analysis["is_empty"] = False
                    break
            except:
                pass
                
        return analysis
        
    def log_chunk(self, chunk: Any, chunk_info: Dict[str, Any]):
        """Log detailed chunk information"""
        self.metrics["chunks_received"] += 1
        
        # Track chunk type
        chunk_type = chunk_info["type"]
        self.metrics["chunk_types"][chunk_type] = self.metrics["chunk_types"].get(chunk_type, 0) + 1
        
        # Track extraction method
        if chunk_info["extraction_method"]:
            method = chunk_info["extraction_method"]
            self.metrics["extraction_methods"][method] = self.metrics["extraction_methods"].get(method, 0) + 1
            
        # Track content vs empty
        if chunk_info["is_empty"]:
            self.metrics["empty_chunks"] += 1
        else:
            if chunk_info["content"]:
                self.metrics["content_chunks"] += 1
                self.metrics["bytes_received"] += chunk_info["content_length"]
            if chunk_info["has_tool_calls"]:
                self.metrics["tool_chunks"] += 1
                
        # Track timing
        current_time = time.time()
        time_since_last = current_time - self.last_chunk_time
        self.metrics["timing"].append(time_since_last)
        self.last_chunk_time = current_time
        
        # Log if enabled
        if self.debug_enabled:
            print(f"[{self.request_id}] 📦 Chunk #{self.metrics['chunks_received']}: "
                  f"{chunk_type} | Empty: {chunk_info['is_empty']} | "
                  f"Method: {chunk_info['extraction_method']} | "
                  f"Content: {chunk_info['content_length']} bytes")
            
            if self.verbose and chunk_info["content"]:
                preview = str(chunk_info["content"])[:50]
                print(f"[{self.request_id}] 💬 Content preview: '{preview}...'")
                print(f"[{self.request_id}] 🔍 Raw chunk: {chunk_info['raw_repr']}")
                
    def log_error(self, error: Exception, context: str = ""):
        """Log an error during streaming"""
        error_info = {
            "timestamp": time.time(),
            "error": str(error),
            "type": type(error).__name__,
            "context": context,
            "chunks_at_error": self.metrics["chunks_received"]
        }
        self.metrics["errors"].append(error_info)
        
        if self.debug_enabled:
            print(f"[{self.request_id}] ❌ ERROR: {context} - {error}")
                
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive debugging summary"""
        duration = time.time() - self.start_time
        avg_timing = sum(self.metrics["timing"]) / len(self.metrics["timing"]) if self.metrics["timing"] else 0
        
        return {
            "request_id": self.request_id,
            "mode": self.mode,
            "model": self.model,
            "duration_seconds": round(duration, 2),
            "chunks_received": self.metrics["chunks_received"],
            "empty_chunks": self.metrics["empty_chunks"],
            "content_chunks": self.metrics["content_chunks"],
            "tool_chunks": self.metrics["tool_chunks"],
            "bytes_received": self.metrics["bytes_received"],
            "empty_ratio": round(self.metrics["empty_chunks"] / self.metrics["chunks_received"], 2) if self.metrics["chunks_received"] > 0 else 0,
            "avg_chunk_interval_ms": round(avg_timing * 1000, 2),
            "chunk_types": self.metrics["chunk_types"],
            "extraction_methods": self.metrics["extraction_methods"],
            "errors": self.metrics["errors"]
        }

    def save_summary_to_file(self):
        """Save summary to debug file if configured"""
        summary_file = os.getenv("DEBUG_STREAMING_SUMMARY")
        if summary_file:
            try:
                summary = self.get_summary()
                with open(summary_file, 'a') as f:
                    f.write(json.dumps({
                        "timestamp": datetime.now().isoformat(),
                        **summary
                    }) + "\n")
            except Exception as e:
                print(f"Failed to write streaming summary: {e}")


def debug_llm_response(response: Any, request_id: str) -> Dict[str, Any]:
    """Debug a single LLM response object"""
    debug_info = {
        "type": type(response).__name__,
        "attributes": [],
        "content_found": False,
        "tool_calls_found": False,
        "extraction_attempts": []
    }
    
    # List all attributes
    if hasattr(response, '__dict__'):
        debug_info["attributes"] = list(response.__dict__.keys())
    
    # Try to extract content using various methods
    extraction_methods = [
        ("direct_content", lambda r: getattr(r, 'content', None)),
        ("choices[0].delta.content", lambda r: r.choices[0].delta.content if hasattr(r, 'choices') and r.choices and hasattr(r.choices[0], 'delta') else None),
        ("choices[0].message.content", lambda r: r.choices[0].message.content if hasattr(r, 'choices') and r.choices and hasattr(r.choices[0], 'message') else None),
        ("delta.content", lambda r: r.delta.content if hasattr(r, 'delta') else None),
        ("text", lambda r: getattr(r, 'text', None)),
        ("message", lambda r: getattr(r, 'message', None)),
    ]
    
    for method_name, extractor in extraction_methods:
        try:
            content = extractor(response)
            debug_info["extraction_attempts"].append({
                "method": method_name,
                "success": content is not None,
                "content_preview": str(content)[:50] if content else None
            })
            if content:
                debug_info["content_found"] = True
        except Exception as e:
            debug_info["extraction_attempts"].append({
                "method": method_name,
                "success": False,
                "error": str(e)
            })
    
    return debug_info 