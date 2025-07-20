#!/usr/bin/env python3
"""
Claude Log Converter
Converts Claude JSONL logs to human-readable Markdown format.
"""

import json
import argparse
from datetime import datetime
from pathlib import Path
import sys


def format_timestamp(timestamp_str):
    """Convert ISO timestamp to readable format."""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return timestamp_str


def format_message_content(content, presentation_mode=False):
    """Format message content based on its type."""
    if isinstance(content, str):
        # Highlight user interruptions with special formatting
        if "[Request interrupted by user]" in content:
            return f"🛑 **{content}**"
        elif "[Request interrupted by user for tool use]" in content:
            return f"⏸️ **{content}**"
        return content
    elif isinstance(content, list):
        formatted_parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get('type') == 'text':
                    text = part.get('text', '')
                    # Highlight user interruptions with special formatting
                    if "[Request interrupted by user]" in text:
                        formatted_parts.append(f"🛑 **{text}**")
                    elif "[Request interrupted by user for tool use]" in text:
                        formatted_parts.append(f"⏸️ **{text}**")
                    else:
                        formatted_parts.append(text)
                elif part.get('type') == 'tool_use':
                    if not presentation_mode:
                        tool_name = part.get('name', 'unknown_tool')
                        tool_input = part.get('input', {})
                        formatted_parts.append(f"**Tool Use: {tool_name}**\n```json\n{json.dumps(tool_input, indent=2)}\n```")
                    # Skip tool_use in presentation mode
                elif part.get('type') == 'tool_result':
                    if not presentation_mode:
                        formatted_parts.append(f"*[{part.get('type', 'unknown')} content]*")
                    # Skip tool_result in presentation mode
                else:
                    if not presentation_mode:
                        formatted_parts.append(f"*[{part.get('type', 'unknown')} content]*")
                    # Skip unknown types in presentation mode
            else:
                text = str(part)
                # Highlight user interruptions with special formatting
                if "[Request interrupted by user]" in text:
                    formatted_parts.append(f"🛑 **{text}**")
                elif "[Request interrupted by user for tool use]" in text:
                    formatted_parts.append(f"⏸️ **{text}**")
                else:
                    formatted_parts.append(text)
        return '\n\n'.join(formatted_parts)
    else:
        text = str(content)
        # Highlight user interruptions with special formatting
        if "[Request interrupted by user]" in text:
            return f"🛑 **{text}**"
        elif "[Request interrupted by user for tool use]" in text:
            return f"⏸️ **{text}**"
        return text


def is_file_update_message(content):
    """Check if a message contains file update information."""
    if isinstance(content, str):
        return any(phrase in content.lower() for phrase in [
            'file created successfully', 'file updated successfully', 
            'the file', 'has been updated', 'has been created', 'successfully'
        ])
    elif isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                if part.get('type') == 'text':
                    text = part.get('text', '').lower()
                    if any(phrase in text for phrase in [
                        'file created successfully', 'file updated successfully',
                        'the file', 'has been updated', 'has been created', 'successfully'
                    ]):
                        return True
                elif part.get('type') == 'tool_use':
                    # Check if it's a file editing tool
                    tool_name = part.get('name', '').lower()
                    if tool_name in ['edit', 'write', 'multiedit', 'todowrite']:
                        return True
                elif part.get('type') == 'tool_result':
                    # Check tool result content for file operations
                    result_content = part.get('content', '').lower()
                    if any(phrase in result_content for phrase in [
                        'file created successfully', 'file updated successfully',
                        'has been updated', 'successfully', 'created', 'modified'
                    ]):
                        return True
    return False


def format_file_update(content):
    """Format file update messages with highlighting."""
    if isinstance(content, str):
        return f"✅ {content}"
    elif isinstance(content, list):
        formatted_parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get('type') == 'text':
                    text = part.get('text', '')
                    formatted_parts.append(f"✅ {text}")
                elif part.get('type') == 'tool_use':
                    tool_name = part.get('name', '')
                    tool_input = part.get('input', {})
                    file_path = tool_input.get('file_path', '')
                    
                    if tool_name.lower() == 'todowrite':
                        # Show todos being created
                        todos = tool_input.get('todos', [])
                        formatted_parts.append(f"📋 **Created Todos:**")
                        for todo in todos:
                            status = todo.get('status', 'pending')
                            content = todo.get('content', '')
                            priority = todo.get('priority', 'medium')
                            formatted_parts.append(f"- [{status}] {content} ({priority})")
                    elif tool_name.lower() == 'write' and file_path:
                        # Show file creation with full content
                        filename = file_path.split('/')[-1]
                        content = tool_input.get('content', '')
                        formatted_parts.append(f"🔧 **{tool_name}**: `{filename}`")
                        if content:
                            # Determine file type for syntax highlighting
                            if filename.endswith(('.ts', '.tsx')):
                                lang = 'typescript'
                            elif filename.endswith(('.js', '.jsx')):
                                lang = 'javascript'
                            elif filename.endswith('.md'):
                                lang = 'markdown'
                            elif filename.endswith('.json'):
                                lang = 'json'
                            else:
                                lang = 'text'
                            formatted_parts.append(f"```{lang}\n{content}\n```")
                    elif tool_name.lower() in ['edit', 'multiedit'] and file_path:
                        # Show Edit/MultiEdit operations with change details
                        filename = file_path.split('/')[-1]
                        formatted_parts.append(f"🔧 **{tool_name}**: `{filename}`")
                        
                        # Show edits for MultiEdit
                        if tool_name.lower() == 'multiedit':
                            edits = tool_input.get('edits', [])
                            if edits:
                                formatted_parts.append(f"**Changes ({len(edits)} edits):**")
                                for i, edit in enumerate(edits[:3]):  # Show first 3 edits
                                    old_str = edit.get('old_string', '')[:100]  # First 100 chars
                                    new_str = edit.get('new_string', '')[:100]
                                    if len(old_str) > 97:
                                        old_str = old_str[:97] + "..."
                                    if len(new_str) > 97:
                                        new_str = new_str[:97] + "..."
                                    formatted_parts.append(f"**Edit {i+1}:**")
                                    formatted_parts.append(f"```diff\n- {old_str}\n+ {new_str}\n```")
                                if len(edits) > 3:
                                    formatted_parts.append(f"*... and {len(edits) - 3} more edits*")
                        # Show single edit for Edit tool
                        elif tool_name.lower() == 'edit':
                            old_str = tool_input.get('old_string', '')[:100]
                            new_str = tool_input.get('new_string', '')[:100]
                            if old_str and new_str:
                                if len(old_str) > 97:
                                    old_str = old_str[:97] + "..."
                                if len(new_str) > 97:
                                    new_str = new_str[:97] + "..."
                                formatted_parts.append(f"```diff\n- {old_str}\n+ {new_str}\n```")
                    elif file_path:
                        # Other file operations
                        filename = file_path.split('/')[-1]
                        formatted_parts.append(f"🔧 **{tool_name}**: `{filename}`")
                    else:
                        formatted_parts.append(f"🔧 **{tool_name}**")
                elif part.get('type') == 'tool_result':
                    result_content = part.get('content', '')
                    # Extract file path if present
                    if 'File created successfully at:' in result_content:
                        formatted_parts.append(f"✅ {result_content}")
                    elif 'has been updated' in result_content:
                        formatted_parts.append(f"✅ {result_content}")
                    else:
                        formatted_parts.append(f"✅ {result_content}")
                else:
                    formatted_parts.append(str(part))
            else:
                formatted_parts.append(str(part))
        return '\n\n'.join(formatted_parts)
    else:
        return f"✅ {str(content)}"


def calculate_session_stats(lines):
    """Calculate session statistics from log lines."""
    stats = {
        'total_messages': 0,
        'user_messages': 0,
        'assistant_messages': 0,
        'file_operations': 0,
        'start_time': None,
        'end_time': None,
        'session_duration': None,
        'estimated_input_tokens': 0,
        'estimated_output_tokens': 0,
        'estimated_total_tokens': 0
    }
    
    for line in lines:
        try:
            data = json.loads(line.strip())
            
            # Skip meta messages
            if data.get('isMeta') or 'message' not in data:
                continue
                
            message = data['message']
            content = message.get('content', '')
            
            # Skip empty messages
            if not content:
                continue
                
            # Track timestamps
            timestamp = data.get('timestamp')
            if timestamp:
                if stats['start_time'] is None:
                    stats['start_time'] = timestamp
                stats['end_time'] = timestamp
            
            # Count messages by role and estimate tokens
            role = message.get('role', '')
            
            # Estimate tokens for this message (improved approximation: 1 token ≈ 3 characters)
            message_tokens = 0
            if isinstance(content, str):
                message_tokens = len(content) // 3
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        if part.get('type') == 'text':
                            message_tokens += len(part.get('text', '')) // 3
                        elif part.get('type') == 'tool_use':
                            # Count tool use parameters (file paths, inputs, etc.)
                            tool_input = part.get('input', {})
                            tool_text = json.dumps(tool_input)
                            message_tokens += len(tool_text) // 3
                        elif part.get('type') == 'tool_result':
                            # Count tool results (file contents, outputs, etc.)
                            result_content = str(part.get('content', ''))
                            message_tokens += len(result_content) // 3
            
            if role == 'user':
                stats['user_messages'] += 1
                stats['estimated_input_tokens'] += message_tokens
            elif role == 'assistant':
                stats['assistant_messages'] += 1
                stats['estimated_output_tokens'] += message_tokens
                
            stats['total_messages'] += 1
            
            # Add overhead for message structure, system context, etc. (roughly 20% overhead)
            message_tokens_with_overhead = int(message_tokens * 1.2)
            stats['estimated_total_tokens'] += message_tokens_with_overhead
            
            # Count file operations
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get('type') == 'tool_use':
                        tool_name = part.get('name', '').lower()
                        if tool_name in ['write', 'edit', 'multiedit']:
                            stats['file_operations'] += 1
                            
        except:
            continue
    
    # Calculate session duration
    if stats['start_time'] and stats['end_time']:
        try:
            start_dt = datetime.fromisoformat(stats['start_time'].replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(stats['end_time'].replace('Z', '+00:00'))
            duration = end_dt - start_dt
            
            # Format duration
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                stats['session_duration'] = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                stats['session_duration'] = f"{minutes}m {seconds}s"
            else:
                stats['session_duration'] = f"{seconds}s"
                
        except:
            stats['session_duration'] = "Unknown"
    
    return stats


def convert_log_to_markdown(jsonl_file, output_file=None, presentation_mode=False):
    """Convert JSONL log file to Markdown format."""
    input_path = Path(jsonl_file)
    
    if not input_path.exists():
        print(f"Error: File {jsonl_file} not found")
        return False
    
    if output_file is None:
        output_file = input_path.with_suffix('.md')
    
    output_path = Path(output_file)
    
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Calculate session statistics
        stats = calculate_session_stats(lines)
        
        # First pass to count actual messages for display
        message_count = 0
        for line in lines:
            try:
                data = json.loads(line.strip())
                if (data.get('isMeta') or (data.get('type') == 'user' and not data.get('message')) 
                    or 'message' not in data or not data['message'].get('content')):
                    continue
                
                # Handle sidechain messages
                if data.get('isSidechain', False):
                    if presentation_mode:
                        # Only count file updates from sidechains in presentation mode
                        if data.get('message', {}).get('role') == 'assistant' and is_file_update_message(data['message'].get('content')):
                            message_count += 1
                    continue
                
                # In presentation mode, also check if content would be empty after filtering
                if presentation_mode:
                    # Always count file updates in main session
                    if data.get('message', {}).get('role') == 'assistant' and is_file_update_message(data['message'].get('content')):
                        message_count += 1
                        continue
                        
                    test_content = format_message_content(data['message']['content'], presentation_mode)
                    if not test_content.strip():
                        continue
                
                message_count += 1
            except:
                continue
        
        with open(output_path, 'w', encoding='utf-8') as f:
            # Write header with session statistics
            f.write(f"# Claude Conversation Log\n\n")
            f.write(f"## Session Statistics\n\n")
            f.write(f"**Source File:** `{input_path.name}`\n")
            f.write(f"**Converted:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Session Duration:** {stats['session_duration'] or 'Unknown'}\n")
            f.write(f"**Total Messages:** {stats['total_messages']}\n")
            f.write(f"**User Messages:** {stats['user_messages']}\n")
            f.write(f"**Assistant Messages:** {stats['assistant_messages']}\n")
            f.write(f"**File Operations:** {stats['file_operations']}\n")
            f.write(f"**Estimated Input Tokens:** {stats['estimated_input_tokens']:,}\n")
            f.write(f"**Estimated Output Tokens:** {stats['estimated_output_tokens']:,}\n")
            f.write(f"**Estimated Total Tokens:** {stats['estimated_total_tokens']:,}\n")
            if stats['start_time']:
                f.write(f"**Session Start:** {format_timestamp(stats['start_time'])}\n")
            if stats['end_time']:
                f.write(f"**Session End:** {format_timestamp(stats['end_time'])}\n")
            f.write("\n---\n\n")
            sidechain_messages = []
            
            for i, line in enumerate(lines):
                try:
                    data = json.loads(line.strip())
                    
                    # Skip meta messages and system messages
                    if data.get('isMeta') or (data.get('type') == 'user' and not data.get('message')):
                        continue
                    
                    # Only process actual conversation messages
                    if 'message' not in data:
                        continue
                    
                    message = data['message']
                    role = message.get('role', 'unknown')
                    content = message.get('content', '')
                    
                    # Skip empty messages
                    if not content:
                        continue
                    
                    # Check if this is a sidechain (sub-session) message
                    is_sidechain = data.get('isSidechain', False)
                    
                    if is_sidechain:
                        if not presentation_mode:
                            # Collect sidechain messages
                            sidechain_messages.append({
                                'role': role,
                                'content': content,
                                'formatted_content': format_message_content(content, presentation_mode)
                            })
                        else:
                            # In presentation mode, check if this is a file update
                            if role == 'assistant' and is_file_update_message(content):
                                # Write file update immediately
                                f.write(f"📝 File Update\n\n")
                                formatted_content = format_file_update(content)
                                f.write(f"{formatted_content}\n\n")
                                f.write("---\n\n")
                        # Skip other sidechain messages if presentation_mode is True
                    else:
                        # First, write any accumulated sidechain messages
                        if sidechain_messages and not presentation_mode:
                            f.write(f"🔧 Sub-Claude Session\n\n")
                            
                            for sc_msg in sidechain_messages:
                                if sc_msg['role'] == 'user':
                                    f.write(f"**Task:** {sc_msg['formatted_content']}\n\n")
                                elif sc_msg['role'] == 'assistant':
                                    f.write(f"**Response:** {sc_msg['formatted_content']}\n\n")
                            
                            f.write("---\n\n")
                            sidechain_messages = []
                        
                        # Check if this is a file update in main session
                        if presentation_mode and role == 'assistant' and is_file_update_message(content):
                            # Write as file update instead of regular assistant message
                            f.write(f"📝 File Update\n\n")
                            formatted_content = format_file_update(content)
                            f.write(f"{formatted_content}\n\n")
                            f.write("---\n\n")
                            continue
                        
                        # Write content first to check if it's empty
                        formatted_content = format_message_content(content, presentation_mode)
                        
                        # Skip empty messages in presentation mode
                        if presentation_mode and not formatted_content.strip():
                            continue
                        
                        # Check if message is short enough for inline format
                        is_short_message = (
                            len(formatted_content.strip()) <= 80 and
                            '\n' not in formatted_content.strip() and
                            not formatted_content.startswith('🛑') and
                            not formatted_content.startswith('⏸️')
                        )
                        
                        if is_short_message:
                            # Write as inline format
                            if role == 'user':
                                f.write(f"👤 User> {formatted_content.strip()}\n\n")
                            elif role == 'assistant':
                                f.write(f"🤖 Assistant> {formatted_content.strip()}\n\n")
                            else:
                                f.write(f"{role.title()}> {formatted_content.strip()}\n\n")
                        else:
                            # Write block format without ## headers
                            if role == 'user':
                                f.write(f"👤 User\n\n")
                            elif role == 'assistant':
                                f.write(f"🤖 Assistant\n\n")
                            else:
                                f.write(f"{role.title()}\n\n")
                            
                            f.write(f"{formatted_content}\n\n")
                        
                        f.write("---\n\n")
                    
                except json.JSONDecodeError as e:
                    f.write(f"## Error parsing line {i+1}\n\n")
                    f.write(f"```\n{line.strip()}\n```\n\n")
                    f.write(f"Error: {e}\n\n---\n\n")
                except Exception as e:
                    f.write(f"## Error processing line {i+1}\n\n")
                    f.write(f"Error: {e}\n\n---\n\n")
            
            # Write any remaining sidechain messages at the end
            if sidechain_messages and not presentation_mode:
                f.write(f"🔧 Sub-Claude Session\n\n")
                
                for sc_msg in sidechain_messages:
                    if sc_msg['role'] == 'user':
                        f.write(f"**Task:** {sc_msg['formatted_content']}\n\n")
                    elif sc_msg['role'] == 'assistant':
                        f.write(f"**Response:** {sc_msg['formatted_content']}\n\n")
                
                f.write("---\n\n")
        
        print(f"Successfully converted {message_count} messages to {output_path}")
        return True
        
    except Exception as e:
        print(f"Error processing file: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Convert Claude JSONL logs to Markdown')
    parser.add_argument('input_file', help='Path to the JSONL log file')
    parser.add_argument('-o', '--output', help='Output Markdown file (default: input_file.md)')
    parser.add_argument('--presentation-mode', action='store_true', help='Clean presentation mode: hide sub-sessions and tool details')
    
    args = parser.parse_args()
    
    success = convert_log_to_markdown(args.input_file, args.output, args.presentation_mode)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()