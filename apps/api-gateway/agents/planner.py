"""
Intelligent Tool Call Planner - Cursor AI-inspired Agent Planning

This module implements a sophisticated planning layer that analyzes user requests,
creates structured execution plans, and intelligently groups tool calls for optimal
performance and user experience.

Key Features:
- Multi-phase planning (analyze → plan → execute → verify)
- Intelligent tool call grouping and batching
- Execution strategy optimization
- Context-aware plan generation
- Error recovery and plan adaptation
"""

import time
import json
import os
import re
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum

from llm.base import LLMClient
from .tools import TOOLS_REGISTRY


class PlanPhase(Enum):
    """Planning phases following Cursor AI methodology."""
    ANALYZE = "analyze"
    PLAN = "plan"
    EXECUTE = "execute"
    VERIFY = "verify"


class ToolCallStrategy(Enum):
    """Tool call execution strategies."""
    INDIVIDUAL = "individual"  # set_cell for single updates
    SMALL_BATCH = "small_batch"  # set_cells for 5-20 cells
    LARGE_BATCH = "large_batch"  # apply_updates_and_reply for 20+ cells
    PROGRESSIVE = "progressive"  # Mix of strategies with progress updates


@dataclass
class ToolCallGroup:
    """Represents a group of related tool calls."""
    strategy: ToolCallStrategy
    tool_name: str
    calls: List[Dict[str, Any]]
    estimated_duration: float
    spatial_locality: bool  # Are the cells adjacent?
    logical_grouping: str  # Type of grouping (headers, formulas, data, etc.)
    priority: int  # Execution priority (1=highest, 5=lowest)


@dataclass
class ExecutionPlan:
    """Represents a complete execution plan."""
    plan_id: str
    user_intent: str
    phases: List[PlanPhase]
    tool_groups: List[ToolCallGroup]
    estimated_total_duration: float
    complexity_score: int  # 1-10 scale
    requires_streaming: bool
    fallback_strategy: Optional[str] = None
    context_references: List[str] = None


class ContextAnalyzer:
    """
    Analyzes conversation context and user intent for intelligent planning.
    Enhanced version of the orchestrator's ContextAnalyzer.
    """
    
    @staticmethod
    def analyze_user_intent(message: str, history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze user intent with enhanced financial modeling detection.
        """
        message_lower = message.lower().strip()
        
        # Enhanced intent patterns
        intent_patterns = {
            'financial_modeling': [
                r'(?i)\b(income statement|profit.{0,5}loss|p.{0,2}l|financial model|financial statement)\b',
                r'(?i)\b(dcf|discounted cash flow|valuation|financial model)\b',
                r'(?i)\b(fsm|financial statement model|three statement model)\b',
                r'(?i)\b(balance sheet|cash flow statement|statement of cash flows)\b',
                r'(?i)\b(wacc|cost of capital|discount rate|terminal value)\b',
                r'(?i)\b(revenue model|cost model|pricing model)\b',
            ],
            'data_analysis': [
                r'(?i)\b(analyze|analysis|examine|investigate|explore)\b',
                r'(?i)\b(trend|pattern|correlation|statistics|metrics)\b',
                r'(?i)\b(calculate|compute|derive|determine)\b',
                r'(?i)\b(summarize|aggregate|total|average|sum)\b',
            ],
            'model_building': [
                r'(?i)\b(build|create|generate|make|construct|design)\b',
                r'(?i)\b(model|template|framework|structure)\b',
                r'(?i)\b(scenario|projection|forecast|estimate)\b',
            ],
            'data_manipulation': [
                r'(?i)\b(update|modify|change|edit|adjust)\b',
                r'(?i)\b(add|insert|remove|delete|copy|move)\b',
                r'(?i)\b(format|style|organize|arrange)\b',
            ],
            'visualization': [
                r'(?i)\b(chart|graph|plot|visualize|display)\b',
                r'(?i)\b(table|dashboard|report|summary)\b',
            ]
        }
        
        # Calculate intent scores
        intent_scores = {}
        for intent, patterns in intent_patterns.items():
            score = 0
            for pattern in patterns:
                matches = re.findall(pattern, message)
                if matches:
                    score += len(matches) * (3 if intent == 'financial_modeling' else 2)
            intent_scores[intent] = score
        
        # Determine primary intent
        primary_intent = max(intent_scores, key=intent_scores.get) if any(intent_scores.values()) else 'general'
        
        # Analyze complexity indicators
        complexity_indicators = {
            'multiple_sheets': len(re.findall(r'(?i)\b(sheet|tab|worksheet)\b', message)),
            'multiple_models': len(re.findall(r'(?i)\b(model|template|framework)\b', message)),
            'time_periods': len(re.findall(r'(?i)\b(year|month|quarter|period|forecast)\b', message)),
            'calculations': len(re.findall(r'(?i)\b(calculate|formula|equation|function)\b', message)),
            'data_size': len(re.findall(r'(?i)\b(rows?|columns?|cells?|range)\b', message)),
        }
        
        complexity_score = min(10, sum(complexity_indicators.values()))
        
        # Estimate scope
        scope_indicators = [
            ('comprehensive', r'(?i)\b(comprehensive|complete|full|entire|whole)\b'),
            ('detailed', r'(?i)\b(detailed|thorough|in-depth|extensive)\b'),
            ('basic', r'(?i)\b(basic|simple|quick|brief|summary)\b'),
            ('complex', r'(?i)\b(complex|advanced|sophisticated|elaborate)\b'),
        ]
        
        scope = 'medium'
        for scope_type, pattern in scope_indicators:
            if re.search(pattern, message):
                scope = scope_type
                break
        
        return {
            'primary_intent': primary_intent,
            'intent_scores': intent_scores,
            'complexity_score': complexity_score,
            'scope': scope,
            'complexity_indicators': complexity_indicators,
            'message_length': len(message.split()),
            'requires_context': any(word in message_lower for word in ['this', 'that', 'above', 'previous', 'last'])
        }


class ToolCallGroupingEngine:
    """
    Intelligent tool call grouping engine that determines optimal batching strategies.
    """
    
    def __init__(self):
        self.grouping_thresholds = {
            'individual_max': 4,      # Use set_cell for <= 4 updates
            'small_batch_max': 20,    # Use set_cells for 5-20 updates
            'large_batch_min': 21,    # Use apply_updates_and_reply for 21+ updates
            'spatial_distance': 5,    # Cells within 5 positions are "adjacent"
            'logical_group_bonus': 2, # Bonus for logical grouping
        }
    
    def analyze_spatial_locality(self, cells: List[str]) -> Dict[str, Any]:
        """
        Analyze spatial relationships between cells.
        """
        if not cells:
            return {'has_locality': False, 'clusters': []}
        
        # Parse cell references
        cell_coords = []
        for cell in cells:
            if isinstance(cell, str) and re.match(r'^[A-Z]+\d+$', cell):
                col_match = re.match(r'^([A-Z]+)', cell)
                row_match = re.search(r'(\d+)$', cell)
                if col_match and row_match:
                    col = col_match.group(1)
                    row = int(row_match.group(1))
                    # Convert column letters to number (A=1, B=2, etc.)
                    col_num = sum((ord(c) - ord('A') + 1) * (26 ** i) 
                                 for i, c in enumerate(reversed(col)))
                    cell_coords.append((col_num, row, cell))
        
        if len(cell_coords) < 2:
            return {'has_locality': False, 'clusters': [cells]}
        
        # Cluster nearby cells
        clusters = []
        remaining_coords = cell_coords[:]
        
        while remaining_coords:
            current_cluster = [remaining_coords.pop(0)]
            changed = True
            
            while changed:
                changed = False
                for coord in remaining_coords[:]:
                    # Check if this coordinate is close to any in current cluster
                    for cluster_coord in current_cluster:
                        col_dist = abs(coord[0] - cluster_coord[0])
                        row_dist = abs(coord[1] - cluster_coord[1])
                        
                        if (col_dist <= self.grouping_thresholds['spatial_distance'] and 
                            row_dist <= self.grouping_thresholds['spatial_distance']):
                            current_cluster.append(coord)
                            remaining_coords.remove(coord)
                            changed = True
                            break
            
            clusters.append([coord[2] for coord in current_cluster])
        
        return {
            'has_locality': len(clusters) < len(cell_coords) / 2,  # More than 50% clustering
            'clusters': clusters,
            'cluster_count': len(clusters)
        }
    
    def determine_logical_grouping(self, updates: List[Dict[str, Any]]) -> str:
        """
        Determine the logical grouping type for updates.
        """
        if not updates:
            return 'unknown'
        
        # Analyze update patterns
        patterns = {
            'headers': 0,
            'formulas': 0,
            'data_entry': 0,
            'formatting': 0,
            'calculations': 0,
        }
        
        for update in updates:
            value = str(update.get('value', '')).lower()
            cell = update.get('cell', '')
            
            # Header detection
            if (any(header_word in value for header_word in 
                   ['revenue', 'cost', 'expense', 'total', 'year', 'quarter']) or
                re.match(r'^[A-Z]1$', cell)):  # First row
                patterns['headers'] += 1
            
            # Formula detection
            if value.startswith('='):
                patterns['formulas'] += 1
            
            # Calculation patterns
            if any(calc_word in value for calc_word in 
                  ['sum', 'average', 'total', 'calculate', 'compute']):
                patterns['calculations'] += 1
            
            # Data entry (numbers, simple text)
            if (value.replace('.', '').replace('-', '').isdigit() or 
                (len(value.split()) <= 3 and not value.startswith('='))):
                patterns['data_entry'] += 1
        
        # Return the most common pattern
        return max(patterns, key=patterns.get) if any(patterns.values()) else 'mixed'
    
    def group_tool_calls(self, tool_calls: List[Dict[str, Any]], intent_analysis: Dict[str, Any]) -> List[ToolCallGroup]:
        """
        Group tool calls based on intelligent analysis.
        """
        if not tool_calls:
            return []
        
        # Separate by tool type
        tool_groups = {}
        for call in tool_calls:
            tool_name = call.get('name', 'unknown')
            if tool_name not in tool_groups:
                tool_groups[tool_name] = []
            tool_groups[tool_name].append(call)
        
        grouped_calls = []
        
        for tool_name, calls in tool_groups.items():
            if tool_name in ['set_cell', 'set_cells', 'apply_updates_and_reply']:
                # Special handling for cell update tools
                grouped_calls.extend(self._group_cell_updates(calls, intent_analysis))
            else:
                # Other tools - group by logical similarity
                grouped_calls.extend(self._group_other_tools(tool_name, calls, intent_analysis))
        
        return grouped_calls
    
    def _group_cell_updates(self, calls: List[Dict[str, Any]], intent_analysis: Dict[str, Any]) -> List[ToolCallGroup]:
        """
        Intelligently group cell update calls.
        """
        # Extract all cell updates
        all_updates = []
        for call in calls:
            args = call.get('args', {})
            if 'updates' in args:
                all_updates.extend(args['updates'])
            elif 'cell' in args and 'value' in args:
                all_updates.append({'cell': args['cell'], 'value': args['value']})
        
        if not all_updates:
            return []
        
        # Analyze spatial and logical grouping
        cells = [update.get('cell', '') for update in all_updates]
        spatial_analysis = self.analyze_spatial_locality(cells)
        logical_grouping = self.determine_logical_grouping(all_updates)
        
        # Determine strategy based on size and characteristics
        update_count = len(all_updates)
        complexity_score = intent_analysis.get('complexity_score', 5)
        
        groups = []
        
        if update_count <= self.grouping_thresholds['individual_max']:
            # Use individual set_cell calls for real-time feedback
            for update in all_updates:
                groups.append(ToolCallGroup(
                    strategy=ToolCallStrategy.INDIVIDUAL,
                    tool_name='set_cell',
                    calls=[{
                        'name': 'set_cell',
                        'args': {'cell': update['cell'], 'value': update['value']}
                    }],
                    estimated_duration=0.5,
                    spatial_locality=False,
                    logical_grouping=logical_grouping,
                    priority=1
                ))
        
        elif update_count <= self.grouping_thresholds['small_batch_max']:
            # Use set_cells for small batches
            if spatial_analysis['has_locality'] and len(spatial_analysis['clusters']) > 1:
                # Create groups based on spatial clusters
                for cluster_cells in spatial_analysis['clusters']:
                    cluster_updates = [u for u in all_updates if u['cell'] in cluster_cells]
                    if cluster_updates:
                        groups.append(ToolCallGroup(
                            strategy=ToolCallStrategy.SMALL_BATCH,
                            tool_name='set_cells',
                            calls=[{
                                'name': 'set_cells',
                                'args': {'updates': cluster_updates}
                            }],
                            estimated_duration=1.0 + len(cluster_updates) * 0.1,
                            spatial_locality=True,
                            logical_grouping=logical_grouping,
                            priority=2
                        ))
            else:
                # Single batch for small updates
                groups.append(ToolCallGroup(
                    strategy=ToolCallStrategy.SMALL_BATCH,
                    tool_name='set_cells',
                    calls=[{
                        'name': 'set_cells',
                        'args': {'updates': all_updates}
                    }],
                    estimated_duration=1.0 + len(all_updates) * 0.1,
                    spatial_locality=spatial_analysis['has_locality'],
                    logical_grouping=logical_grouping,
                    priority=2
                ))
        
        else:
            # Use apply_updates_and_reply for large operations
            reply_message = self._generate_batch_reply(intent_analysis, logical_grouping, update_count)
            groups.append(ToolCallGroup(
                strategy=ToolCallStrategy.LARGE_BATCH,
                tool_name='apply_updates_and_reply',
                calls=[{
                    'name': 'apply_updates_and_reply',
                    'args': {
                        'updates': all_updates,
                        'reply': reply_message
                    }
                }],
                estimated_duration=2.0 + len(all_updates) * 0.05,
                spatial_locality=spatial_analysis['has_locality'],
                logical_grouping=logical_grouping,
                priority=3
            ))
        
        return groups
    
    def _group_other_tools(self, tool_name: str, calls: List[Dict[str, Any]], intent_analysis: Dict[str, Any]) -> List[ToolCallGroup]:
        """
        Group non-cell-update tools.
        """
        # For most tools, execute individually but group by logical similarity
        complexity = intent_analysis.get('complexity_score', 5)
        
        return [ToolCallGroup(
            strategy=ToolCallStrategy.INDIVIDUAL,
            tool_name=tool_name,
            calls=calls,
            estimated_duration=0.8 * len(calls),
            spatial_locality=False,
            logical_grouping='tool_execution',
            priority=1 if tool_name in ['get_cell', 'get_cells'] else 2
        )]
    
    def _generate_batch_reply(self, intent_analysis: Dict[str, Any], logical_grouping: str, update_count: int) -> str:
        """
        Generate an appropriate reply message for batch updates.
        """
        primary_intent = intent_analysis.get('primary_intent', 'general')
        
        if primary_intent == 'financial_modeling':
            if logical_grouping == 'headers':
                return f"I've set up the financial model structure with {update_count} header cells. The framework is now ready for data input."
            elif logical_grouping == 'formulas':
                return f"I've implemented {update_count} calculation formulas in your financial model. The calculations are now linked and will update automatically."
            elif logical_grouping == 'data_entry':
                return f"I've populated {update_count} data cells in your financial model. You can now see the results and projections."
            else:
                return f"I've completed building your financial model with {update_count} updates. The model is ready for analysis."
        
        elif primary_intent == 'data_analysis':
            return f"I've completed the data analysis with {update_count} updates. The results are now available for review."
        
        elif primary_intent == 'model_building':
            return f"I've constructed the model with {update_count} components. The structure is complete and ready for use."
        
        else:
            return f"I've made {update_count} updates to your spreadsheet. The changes have been applied successfully."


class Planner:
    """
    Main planner class implementing Cursor AI-style intelligent agent planning.
    """
    
    def __init__(self, llm_client: LLMClient = None):
        self.llm = llm_client
        self.context_analyzer = ContextAnalyzer()
        self.grouping_engine = ToolCallGroupingEngine()
        self.plan_cache = {}  # Cache for similar planning requests
        
        # Planning configuration
        self.config = {
            'max_plan_duration': float(os.getenv('MAX_PLAN_DURATION', '300')),  # 5 minutes
            'min_streaming_threshold': int(os.getenv('MIN_STREAMING_THRESHOLD', '5')),  # 5 updates
            'complexity_threshold': int(os.getenv('COMPLEXITY_THRESHOLD', '7')),  # 1-10 scale
            'enable_progressive_disclosure': os.getenv('ENABLE_PROGRESSIVE_DISCLOSURE', '1') == '1',
        }
    
    def analyze_request(self, message: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Analyze the user's request to understand intent and requirements.
        
        Args:
            message: User's message
            context: Optional conversation context
            
        Returns:
            Analysis results with intent, complexity, and requirements
        """
        analysis_start = time.time()
        planner_id = f"plan-{int(analysis_start * 1000)}"
        
        print(f"[{planner_id}] 🧠 Analyzing user request: {message[:100]}...")
        
        # Analyze user intent
        intent_analysis = self.context_analyzer.analyze_user_intent(message, context.get('history', []) if context else [])
        
        # Extract specific requirements
        requirements = self._extract_requirements(message, intent_analysis)
        
        # Estimate resource needs
        resource_estimation = self._estimate_resources(requirements, intent_analysis)
        
        analysis_result = {
            'planner_id': planner_id,
            'intent_analysis': intent_analysis,
            'requirements': requirements,
            'resource_estimation': resource_estimation,
            'analysis_duration': time.time() - analysis_start,
            'timestamp': time.time()
        }
        
        print(f"[{planner_id}] 📊 Analysis complete: intent={intent_analysis['primary_intent']}, complexity={intent_analysis['complexity_score']}, scope={intent_analysis['scope']}")
        
        return analysis_result
    
    def create_execution_plan(self, analysis: Dict[str, Any], available_tools: List[Dict[str, Any]] = None) -> ExecutionPlan:
        """
        Create a detailed execution plan based on the analysis.
        
        Args:
            analysis: Result from analyze_request
            available_tools: List of available tools
            
        Returns:
            Complete execution plan
        """
        planner_id = analysis['planner_id']
        intent_analysis = analysis['intent_analysis']
        requirements = analysis['requirements']
        
        print(f"[{planner_id}] 📋 Creating execution plan...")
        
        # Determine phases needed
        phases = self._determine_phases(intent_analysis, requirements)
        
        # Generate initial tool calls
        initial_tool_calls = self._generate_tool_calls(requirements, available_tools or [])
        
        # Group tool calls intelligently
        tool_groups = self.grouping_engine.group_tool_calls(initial_tool_calls, intent_analysis)
        
        # Calculate estimates
        estimated_duration = sum(group.estimated_duration for group in tool_groups)
        complexity_score = intent_analysis['complexity_score']
        
        # Determine if streaming is beneficial
        requires_streaming = (
            len(initial_tool_calls) >= self.config['min_streaming_threshold'] or
            estimated_duration > 5.0 or
            complexity_score >= self.config['complexity_threshold']
        )
        
        # Create fallback strategy
        fallback_strategy = self._create_fallback_strategy(intent_analysis, requirements)
        
        plan = ExecutionPlan(
            plan_id=f"{planner_id}-exec",
            user_intent=intent_analysis['primary_intent'],
            phases=phases,
            tool_groups=tool_groups,
            estimated_total_duration=estimated_duration,
            complexity_score=complexity_score,
            requires_streaming=requires_streaming,
            fallback_strategy=fallback_strategy,
            context_references=requirements.get('context_references', [])
        )
        
        print(f"[{planner_id}] ✅ Execution plan created: {len(tool_groups)} groups, {estimated_duration:.1f}s estimated, streaming={requires_streaming}")
        
        return plan
    
    def validate_plan(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """
        Validate the execution plan for feasibility and safety.
        """
        validation_start = time.time()
        print(f"[{plan.plan_id}] 🔍 Validating execution plan...")
        
        issues = []
        warnings = []
        
        # Check duration limits
        if plan.estimated_total_duration > self.config['max_plan_duration']:
            issues.append(f"Plan duration ({plan.estimated_total_duration:.1f}s) exceeds maximum ({self.config['max_plan_duration']}s)")
        
        # Check tool group validity
        for i, group in enumerate(plan.tool_groups):
            if not group.calls:
                issues.append(f"Tool group {i} has no calls")
            
            if group.estimated_duration > 60:  # 1 minute per group
                warnings.append(f"Tool group {i} has long estimated duration ({group.estimated_duration:.1f}s)")
            
            # Validate tool calls
            for call in group.calls:
                if 'name' not in call or 'args' not in call:
                    issues.append(f"Invalid tool call format in group {i}: {call}")
        
        # Check complexity vs. capability
        if plan.complexity_score > 8 and len(plan.tool_groups) < 2:
            warnings.append("High complexity score but few tool groups - plan might be underestimating complexity")
        
        validation_result = {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings,
            'validation_duration': time.time() - validation_start,
            'recommendations': self._generate_recommendations(plan, issues, warnings)
        }
        
        if validation_result['is_valid']:
            print(f"[{plan.plan_id}] ✅ Plan validation passed with {len(warnings)} warnings")
        else:
            print(f"[{plan.plan_id}] ❌ Plan validation failed with {len(issues)} issues")
        
        return validation_result
    
    def adapt_plan_for_error(self, plan: ExecutionPlan, error: str, failed_group_index: int) -> Optional[ExecutionPlan]:
        """
        Adapt the plan when an error occurs during execution.
        """
        print(f"[{plan.plan_id}] 🔧 Adapting plan due to error in group {failed_group_index}: {error}")
        
        if failed_group_index >= len(plan.tool_groups):
            return None
        
        failed_group = plan.tool_groups[failed_group_index]
        
        # Create adapted plan
        adapted_groups = plan.tool_groups[:failed_group_index]  # Keep successful groups
        
        # Try to recover failed group
        if failed_group.strategy == ToolCallStrategy.LARGE_BATCH:
            # Break down large batch into smaller ones
            print(f"[{plan.plan_id}] 🔄 Breaking down large batch into smaller groups")
            recovery_groups = self._break_down_large_batch(failed_group)
            adapted_groups.extend(recovery_groups)
        
        elif failed_group.strategy == ToolCallStrategy.SMALL_BATCH:
            # Convert to individual calls
            print(f"[{plan.plan_id}] 🔄 Converting small batch to individual calls")
            recovery_groups = self._convert_to_individual_calls(failed_group)
            adapted_groups.extend(recovery_groups)
        
        else:
            # Skip failed group and continue with remaining
            print(f"[{plan.plan_id}] ⏭️ Skipping failed individual call")
        
        # Add remaining groups
        adapted_groups.extend(plan.tool_groups[failed_group_index + 1:])
        
        # Create new plan
        adapted_plan = ExecutionPlan(
            plan_id=f"{plan.plan_id}-adapted",
            user_intent=plan.user_intent,
            phases=plan.phases,
            tool_groups=adapted_groups,
            estimated_total_duration=sum(g.estimated_duration for g in adapted_groups),
            complexity_score=plan.complexity_score,
            requires_streaming=plan.requires_streaming,
            fallback_strategy=plan.fallback_strategy,
            context_references=plan.context_references
        )
        
        print(f"[{plan.plan_id}] ✅ Plan adapted: {len(adapted_groups)} groups remaining")
        return adapted_plan
    
    def _extract_requirements(self, message: str, intent_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Extract specific requirements from the message."""
        requirements = {
            'data_operations': [],
            'model_operations': [],
            'analysis_operations': [],
            'formatting_operations': [],
            'context_references': [],
            'output_format': 'default',
            'urgency': 'normal'
        }
        
        message_lower = message.lower()
        
        # Data operations
        if re.search(r'(?i)\b(add|insert|create|build)\b.*\b(row|column|cell|data)\b', message):
            requirements['data_operations'].append('create')
        if re.search(r'(?i)\b(update|change|modify|edit)\b.*\b(cell|value|data)\b', message):
            requirements['data_operations'].append('update')
        if re.search(r'(?i)\b(delete|remove|clear)\b.*\b(row|column|cell|data)\b', message):
            requirements['data_operations'].append('delete')
        
        # Model operations
        if re.search(r'(?i)\b(financial model|dcf|fsm|income statement)\b', message):
            requirements['model_operations'].append('financial_model')
        if re.search(r'(?i)\b(formula|calculation|equation)\b', message):
            requirements['model_operations'].append('calculations')
        
        # Context references
        context_phrases = ['this', 'that', 'above', 'previous', 'last', 'it']
        for phrase in context_phrases:
            if phrase in message_lower:
                requirements['context_references'].append(phrase)
        
        # Urgency indicators
        if any(urgent in message_lower for urgent in ['quick', 'fast', 'urgent', 'asap', 'immediately']):
            requirements['urgency'] = 'high'
        elif any(careful in message_lower for careful in ['careful', 'detailed', 'thorough', 'comprehensive']):
            requirements['urgency'] = 'low'
        
        return requirements
    
    def _estimate_resources(self, requirements: Dict[str, Any], intent_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Estimate resource requirements for the request."""
        base_complexity = intent_analysis['complexity_score']
        
        # Adjust based on operations
        operation_multipliers = {
            'create': 1.2,
            'update': 1.0,
            'delete': 0.8,
            'financial_model': 2.0,
            'calculations': 1.5,
        }
        
        complexity_multiplier = 1.0
        for op_list in requirements.values():
            if isinstance(op_list, list):
                for op in op_list:
                    complexity_multiplier *= operation_multipliers.get(op, 1.0)
        
        estimated_complexity = min(10, base_complexity * complexity_multiplier)
        
        return {
            'estimated_complexity': estimated_complexity,
            'estimated_tool_calls': max(1, int(estimated_complexity * 2)),
            'estimated_duration': max(1.0, estimated_complexity * 3),
            'memory_requirements': 'low' if estimated_complexity < 5 else 'medium' if estimated_complexity < 8 else 'high'
        }
    
    def _determine_phases(self, intent_analysis: Dict[str, Any], requirements: Dict[str, Any]) -> List[PlanPhase]:
        """Determine which phases are needed for execution."""
        phases = [PlanPhase.ANALYZE, PlanPhase.PLAN]
        
        # Always need execute phase
        phases.append(PlanPhase.EXECUTE)
        
        # Add verify phase for complex operations
        if (intent_analysis['complexity_score'] >= 6 or
            'financial_model' in requirements.get('model_operations', []) or
            requirements.get('urgency') == 'low'):
            phases.append(PlanPhase.VERIFY)
        
        return phases
    
    def _generate_tool_calls(self, requirements: Dict[str, Any], available_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate initial tool calls based on requirements."""
        tool_calls = []
        
        # This is a simplified version - in practice, this would be much more sophisticated
        # and would integrate with the actual tool analysis and execution logic
        
        # For now, return empty list as tool calls will be generated by the agent itself
        # This method provides the framework for future intelligent tool call generation
        
        return tool_calls
    
    def _create_fallback_strategy(self, intent_analysis: Dict[str, Any], requirements: Dict[str, Any]) -> str:
        """Create a fallback strategy if the main plan fails."""
        primary_intent = intent_analysis['primary_intent']
        
        if primary_intent == 'financial_modeling':
            return "If complex model building fails, break down into individual component creation and step-by-step assembly"
        elif primary_intent == 'data_analysis':
            return "If bulk analysis fails, perform analysis on data subsets and aggregate results"
        elif primary_intent == 'model_building':
            return "If automated model building fails, guide user through manual construction steps"
        else:
            return "If batch operations fail, fall back to individual operations with manual confirmation"
    
    def _generate_recommendations(self, plan: ExecutionPlan, issues: List[str], warnings: List[str]) -> List[str]:
        """Generate recommendations for plan improvement."""
        recommendations = []
        
        if plan.estimated_total_duration > 30:
            recommendations.append("Consider breaking down the operation into smaller steps for better user feedback")
        
        if plan.complexity_score > 7:
            recommendations.append("High complexity detected - ensure adequate error handling and user communication")
        
        if len(plan.tool_groups) > 10:
            recommendations.append("Many tool groups detected - consider consolidating related operations")
        
        if any("duration" in issue.lower() for issue in issues):
            recommendations.append("Reduce scope or implement progressive execution to meet timing constraints")
        
        return recommendations
    
    def _break_down_large_batch(self, failed_group: ToolCallGroup) -> List[ToolCallGroup]:
        """Break down a failed large batch into smaller groups."""
        recovery_groups = []
        
        for call in failed_group.calls:
            if call['name'] == 'apply_updates_and_reply':
                updates = call['args'].get('updates', [])
                
                # Split into chunks of 10
                chunk_size = 10
                for i in range(0, len(updates), chunk_size):
                    chunk = updates[i:i + chunk_size]
                    recovery_groups.append(ToolCallGroup(
                        strategy=ToolCallStrategy.SMALL_BATCH,
                        tool_name='set_cells',
                        calls=[{
                            'name': 'set_cells',
                            'args': {'updates': chunk}
                        }],
                        estimated_duration=1.0 + len(chunk) * 0.1,
                        spatial_locality=failed_group.spatial_locality,
                        logical_grouping=failed_group.logical_grouping,
                        priority=failed_group.priority
                    ))
        
        return recovery_groups
    
    def _convert_to_individual_calls(self, failed_group: ToolCallGroup) -> List[ToolCallGroup]:
        """Convert a failed batch to individual calls."""
        recovery_groups = []
        
        for call in failed_group.calls:
            if call['name'] == 'set_cells':
                updates = call['args'].get('updates', [])
                
                for update in updates:
                    recovery_groups.append(ToolCallGroup(
                        strategy=ToolCallStrategy.INDIVIDUAL,
                        tool_name='set_cell',
                        calls=[{
                            'name': 'set_cell',
                            'args': {'cell': update['cell'], 'value': update['value']}
                        }],
                        estimated_duration=0.5,
                        spatial_locality=False,
                        logical_grouping=failed_group.logical_grouping,
                        priority=failed_group.priority
                    ))
        
        return recovery_groups 