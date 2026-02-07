#!/usr/bin/env python3
"""
Token Budget Manager

Manages token budgets for LLM operations and applies intelligent truncation
when budgets are exceeded. Uses Bedrock CountTokens API for accurate token counting.

Key Features:
- Accurate token counting via Bedrock API
- Proportional truncation of large agent responses
- Preserves data structure while reducing size
- Maintains first/last items in lists (endpoints are most important)
"""

import boto3
from typing import Any, Dict, List, Tuple
import json

from lib.logger import get_logger

logger = get_logger()


class TokenBudgetManager:
    """
    Manages token budgets and applies proportional truncation when limits exceeded.

    Uses separate model IDs for inference vs token counting:
    - Inference: Cross-region profile (us.anthropic.claude-sonnet-4...)
    - Token counting: Foundation model (anthropic.claude-sonnet-4...)
    """

    def __init__(
        self,
        model_id: str,
        region: str = "us-east-1",
        budget: int = 180_000,
        token_counter_model_id: str = None
    ):
        """
        Initialize TokenBudgetManager.

        Args:
            model_id: Model ID for inference (cross-region profile with us. prefix)
            region: AWS region
            budget: Maximum token budget (default 180K)
            token_counter_model_id: Model ID for token counting (foundation model, no us. prefix)
                                   If not provided, strips us. prefix from model_id
        """
        self.model_id = model_id
        self.region = region
        self.budget = budget

        # Determine token counter model ID
        if token_counter_model_id:
            self.token_counter_model_id = token_counter_model_id
        else:
            # Strip us. prefix if present
            self.token_counter_model_id = (
                model_id.replace("us.", "", 1) if model_id.startswith("us.") else model_id
            )

        # Create Bedrock runtime client
        self.bedrock_runtime = boto3.client("bedrock-runtime", region_name=region)

        logger.info(
            f"TokenBudgetManager initialized: budget={budget}, "
            f"inference_model={model_id}, token_counter_model={self.token_counter_model_id}"
        )

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using Bedrock CountTokens API.

        Args:
            text: Text to count tokens for

        Returns:
            Number of input tokens
        """
        # Create message structure for CountTokens API
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "text": text
                    }
                ]
            }
        ]

        try:
            # Call CountTokens API with foundation model format (no us. prefix)
            response = self.bedrock_runtime.count_tokens(
                modelId=self.token_counter_model_id,
                input={
                    "converse": {
                        "messages": messages
                    }
                }
            )

            token_count = response["inputTokens"]
            logger.debug(f"Token count: {token_count} tokens (model: {self.token_counter_model_id})")
            return token_count

        except Exception as e:
            logger.error(f"Token counting failed: {e}")
            # Fallback: rough estimate (1 token ≈ 4 characters)
            estimated = len(text) // 4
            logger.warning(f"Using estimated token count: {estimated}")
            return estimated

    def check_budget(self, text: str) -> Tuple[int, bool]:
        """
        Check if text exceeds token budget.

        Args:
            text: Text to check

        Returns:
            Tuple of (token_count, exceeds_budget)
        """
        token_count = self.count_tokens(text)
        exceeds = token_count > self.budget

        if exceeds:
            logger.warning(
                f"Token budget exceeded: {token_count}/{self.budget} tokens "
                f"({(token_count/self.budget - 1)*100:.1f}% over)"
            )

        return token_count, exceeds

    def apply_proportional_truncation(
        self,
        agent_responses: Dict[str, Any],
        reduction_factor: float
    ) -> Dict[str, Any]:
        """
        Apply proportional truncation to agent responses.

        Reduces size of large lists while preserving structure and key data points.
        Keeps first few and last few items to maintain context.

        Args:
            agent_responses: Dict of agent responses to truncate
            reduction_factor: Factor to reduce by (0.5 = 50% reduction)

        Returns:
            Truncated agent responses
        """
        logger.info(
            f"Applying proportional truncation with reduction_factor={reduction_factor}"
        )

        # Estimate size before truncation
        size_before = self._estimate_size(agent_responses)

        # Truncate the responses
        truncated = self._truncate_value(agent_responses, reduction=reduction_factor)

        # Estimate size after truncation
        size_after = self._estimate_size(truncated)

        logger.info(
            f"Truncation complete: {size_before} items → {size_after} items "
            f"({(1 - size_after/max(size_before, 1))*100:.1f}% reduction)"
        )

        return truncated

    def _truncate_value(self, value: Any, reduction: float) -> Any:
        """
        Recursively truncate a value based on its type.

        Args:
            value: Value to truncate (dict, list, or primitive)
            reduction: Reduction factor to apply

        Returns:
            Truncated value
        """
        if isinstance(value, dict):
            return self._truncate_dict(value, reduction)
        elif isinstance(value, list):
            return self._truncate_list(value, reduction)
        else:
            # Primitives (str, int, bool, None) are not truncated
            return value

    def _truncate_dict(self, d: Dict[str, Any], reduction: float) -> Dict[str, Any]:
        """
        Truncate dictionary by recursively truncating its values.

        All keys are preserved - we only truncate values.

        Args:
            d: Dictionary to truncate
            reduction: Reduction factor

        Returns:
            Truncated dictionary
        """
        return {
            key: self._truncate_value(value, reduction)
            for key, value in d.items()
        }

    def _truncate_list(self, lst: List[Any], reduction: float) -> List[Any]:
        """
        Truncate list by sampling items strategically.

        Strategy:
        - Lists <= 3 items: Keep all (too small to truncate meaningfully)
        - Lists > 3 items: Keep first 3, last 2, and sample from middle

        This preserves context (beginning/end are most important) while reducing size.

        Args:
            lst: List to truncate
            reduction: Reduction factor (0.5 = keep 50% of items)

        Returns:
            Truncated list
        """
        if len(lst) <= 3:
            # Too small to truncate meaningfully
            return lst

        # Calculate target length
        target_len = max(3, int(len(lst) * (1 - reduction)))

        if target_len >= len(lst):
            # No truncation needed
            return lst

        # Keep first 3 items (context)
        result = lst[:3]

        # Calculate how many items to sample from middle
        remaining_slots = target_len - 3 - 2  # Reserve 2 for end

        if remaining_slots > 0:
            # Sample from middle section
            middle_section = lst[3:-2]
            if len(middle_section) > 0:
                # Take evenly spaced samples
                step = max(1, len(middle_section) // remaining_slots)
                samples = middle_section[::step][:remaining_slots]
                result.extend(samples)

        # Keep last 2 items (conclusion)
        if len(lst) >= 5:  # Only if list is long enough
            result.extend(lst[-2:])

        return result

    def _estimate_size(self, value: Any) -> int:
        """
        Estimate the "size" of a value for logging purposes.

        Size is defined as:
        - Dict: number of keys + size of all values
        - List: number of items + size of all items
        - Primitive: 0 (not counted)

        Args:
            value: Value to estimate size of

        Returns:
            Estimated size
        """
        if isinstance(value, dict):
            # Count keys plus nested sizes
            return len(value) + sum(self._estimate_size(v) for v in value.values())
        elif isinstance(value, list):
            # Count items plus nested sizes
            return len(value) + sum(self._estimate_size(item) for item in value)
        else:
            # Primitives don't count
            return 0


# Example usage
if __name__ == "__main__":
    # Example: Managing token budget for large responses
    manager = TokenBudgetManager(
        model_id="anthropic.claude-sonnet-4-20250514-v1:0",
        budget=180_000
    )

    # Simulate large agent responses
    large_response = {
        "location-loader": {
            "locations": [
                {"name": f"Restaurant {i}", "lat": 47.6 + i*0.01, "lon": -122.3}
                for i in range(1000)  # 1000 restaurants
            ],
            "total_count": 1000
        },
        "weather-agent": {
            "forecast": [
                {"day": i, "temp": 60 + i, "condition": "rainy"}
                for i in range(7)
            ],
            "city": "Seattle"
        }
    }

    # Convert to text for token counting
    text = json.dumps(large_response)
    token_count, exceeds = manager.check_budget(text)

    print(f"Token count: {token_count}")
    print(f"Exceeds budget: {exceeds}")

    if exceeds:
        # Apply truncation
        reduction = 1 - (manager.budget / token_count)  # Calculate needed reduction
        truncated = manager.apply_proportional_truncation(large_response, reduction)

        print(f"\nTruncated {len(large_response['location-loader']['locations'])} locations")
        print(f"to {len(truncated['location-loader']['locations'])} locations")
