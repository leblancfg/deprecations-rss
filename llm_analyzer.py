"""LLM-powered analysis to improve deprecation content quality."""

import os
import json
from typing import Dict, List
import httpx
from datetime import datetime


class LLMAnalyzer:
    """Analyzes deprecation content using Anthropic's Claude API."""
    
    def __init__(self):
        self.api_key = os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_API_TOKEN')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY or ANTHROPIC_API_TOKEN environment variable required")
        
        self.client = httpx.Client(
            base_url="https://api.anthropic.com",
            headers={
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            },
            timeout=30.0
        )
        
        # Validate API key upfront
        self._validate_api_key()
    
    def _validate_api_key(self):
        """Test API key with minimal token usage before processing data."""
        try:
            response = self.client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 1,  # Minimal token usage
                    "messages": [{
                        "role": "user", 
                        "content": "Hi"
                    }]
                }
            )
            
            if response.status_code != 200:
                raise ValueError(f"Invalid API key: {response.status_code} - {response.text}")
                
        except httpx.RequestError as e:
            raise ValueError(f"API connection failed: {e}")
    
    def analyze_batch(self, items: List[Dict]) -> List[Dict]:
        """
        Analyze a batch of deprecation items efficiently.
        
        Args:
            items: List of deprecation items to analyze
            
        Returns:
            List of enhanced items with LLM analysis
        """
        if not items:
            return []
        
        # Process items in small batches to optimize token usage
        batch_size = 3  # Small batches to avoid token limits
        enhanced_items = []
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            try:
                enhanced_batch = self._analyze_batch_internal(batch)
                enhanced_items.extend(enhanced_batch)
            except Exception as e:
                print(f"LLM analysis failed for batch {i//batch_size + 1}: {e}")
                # Return original items if analysis fails
                enhanced_items.extend(batch)
        
        return enhanced_items
    
    def _analyze_batch_internal(self, items: List[Dict]) -> List[Dict]:
        """Internal method to analyze a small batch of items."""
        
        # Create compact input for the LLM
        input_data = []
        for i, item in enumerate(items):
            input_data.append({
                "id": i,
                "provider": item.get("provider", ""),
                "title": item.get("title", ""),
                "content": item.get("content", "")[:800],  # Limit content length
                "announcement_date": item.get("announcement_date", ""),
                "shutdown_date": item.get("shutdown_date", ""),
            })
        
        prompt = self._create_analysis_prompt(input_data)
        
        try:
            response = self.client.post(
                "/v1/messages",
                json={
                    "model": "claude-3-haiku-20240307",  # Fast, cost-effective model
                    "max_tokens": 1000,  # Conservative limit
                    "messages": [{
                        "role": "user",
                        "content": prompt
                    }]
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                analysis_text = result["content"][0]["text"]
                return self._parse_analysis_response(analysis_text, items)
            else:
                print(f"API Error: {response.status_code} - {response.text}")
                return items
                
        except Exception as e:
            print(f"LLM analysis error: {e}")
            return items
    
    def _create_analysis_prompt(self, input_data: List[Dict]) -> str:
        """Create an efficient prompt for batch analysis."""
        
        items_json = json.dumps(input_data, indent=2)
        
        return f"""Analyze these AI model deprecation notices and improve their titles and content for an RSS feed.

For each item, provide:
1. An improved, concise title (under 80 chars)
2. A clean summary (under 300 chars) 
3. Extract/standardize any dates mentioned

Focus on:
- Making titles more readable and informative
- Removing marketing language and boilerplate
- Highlighting key model names and dates
- Being concise for RSS feed readers

Input deprecations:
{items_json}

Respond with JSON array matching input order:
[
  {{
    "id": 0,
    "improved_title": "Clear, concise title",
    "improved_content": "Clean summary with key details",
    "extracted_dates": {{
      "announcement": "YYYY-MM-DD or empty",
      "shutdown": "YYYY-MM-DD or empty"
    }}
  }},
  ...
]

Only respond with the JSON array, no other text."""
    
    def _parse_analysis_response(self, analysis_text: str, original_items: List[Dict]) -> List[Dict]:
        """Parse LLM response and merge with original items."""
        
        try:
            # Extract JSON from response
            analysis_text = analysis_text.strip()
            if not analysis_text.startswith('['):
                # Try to find JSON in the response
                start = analysis_text.find('[')
                end = analysis_text.rfind(']') + 1
                if start >= 0 and end > start:
                    analysis_text = analysis_text[start:end]
                else:
                    raise ValueError("No JSON array found in response")
            
            analyses = json.loads(analysis_text)
            
            enhanced_items = []
            for i, original in enumerate(original_items):
                if i < len(analyses):
                    analysis = analyses[i]
                    enhanced = original.copy()
                    
                    # Apply improvements
                    if analysis.get("improved_title"):
                        enhanced["title"] = analysis["improved_title"]
                    
                    if analysis.get("improved_content"):
                        enhanced["content"] = analysis["improved_content"]
                    
                    # Update dates if extracted
                    dates = analysis.get("extracted_dates", {})
                    if dates.get("announcement"):
                        enhanced["announcement_date"] = dates["announcement"]
                    if dates.get("shutdown"):
                        enhanced["shutdown_date"] = dates["shutdown"]
                    
                    # Mark as LLM-enhanced
                    enhanced["llm_enhanced"] = True
                    enhanced["llm_enhanced_at"] = datetime.utcnow().isoformat()
                    
                    enhanced_items.append(enhanced)
                else:
                    enhanced_items.append(original)
            
            return enhanced_items
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"Failed to parse LLM response: {e}")
            print(f"Response text: {analysis_text[:200]}...")
            return original_items