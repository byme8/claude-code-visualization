#!/usr/bin/env python3
"""
Claude Log to JSON Converter
Converts Claude JSONL logs to simplified JSON format for interactive visualization.
"""

import json
import argparse
from datetime import datetime
from pathlib import Path
import sys


def extract_file_operations(content):
    """Extract file operation details from message content."""
    operations = []
    
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get('type') == 'tool_use':
                tool_name = part.get('name', '')
                tool_input = part.get('input', {})
                file_path = tool_input.get('file_path', '')
                
                if tool_name.lower() in ['write', 'edit', 'multiedit', 'read', 'todowrite']:
                    operation = {
                        'type': tool_name.lower(),
                        'file_path': file_path,
                        'file_name': file_path.split('/')[-1] if file_path else '',
                    }
                    
                    if tool_name.lower() == 'write':
                        content = tool_input.get('content', '')
                        operation['content_length'] = len(content)
                        operation['language'] = get_language_from_filename(operation['file_name'])
                        # Include full content for write operations
                        operation['content_preview'] = content
                    elif tool_name.lower() in ['edit', 'multiedit']:
                        if tool_name.lower() == 'multiedit':
                            edits = tool_input.get('edits', [])
                            operation['edit_count'] = len(edits)
                            operation['edits'] = [
                                {
                                    'old_string': edit.get('old_string', ''),  # Full content
                                    'new_string': edit.get('new_string', ''),
                                    'replace_all': edit.get('replace_all', False)
                                }
                                for edit in edits  # All edits
                            ]
                        else:
                            operation['edit_count'] = 1
                            old_string = tool_input.get('old_string', '')
                            new_string = tool_input.get('new_string', '')
                            if old_string or new_string:
                                operation['edits'] = [{
                                    'old_string': old_string,
                                    'new_string': new_string,
                                    'replace_all': tool_input.get('replace_all', False)
                                }]
                    elif tool_name.lower() == 'read':
                        operation['offset'] = tool_input.get('offset')
                        operation['limit'] = tool_input.get('limit')
                    elif tool_name.lower() == 'todowrite':
                        todos = tool_input.get('todos', [])
                        operation['todo_count'] = len(todos)
                        operation['todos'] = [
                            {
                                'content': todo.get('content', ''),
                                'status': todo.get('status', 'pending'),
                                'priority': todo.get('priority', 'medium')
                            }
                            for todo in todos
                        ]
                    
                    operations.append(operation)
    
    return operations


def get_language_from_filename(filename):
    """Determine programming language from file extension."""
    if not filename:
        return 'text'
    
    ext = filename.split('.')[-1].lower()
    
    lang_map = {
        'ts': 'typescript',
        'tsx': 'typescript',
        'js': 'javascript',
        'jsx': 'javascript',
        'py': 'python',
        'md': 'markdown',
        'json': 'json',
        'html': 'html',
        'css': 'css',
        'scss': 'scss',
        'yaml': 'yaml',
        'yml': 'yaml',
        'xml': 'xml',
        'sql': 'sql',
        'sh': 'bash',
        'bash': 'bash'
    }
    
    return lang_map.get(ext, 'text')


def extract_text_content(content):
    """Extract plain text from message content."""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get('type') == 'text':
                    text_parts.append(part.get('text', ''))
            else:
                text_parts.append(str(part))
        return '\n'.join(text_parts)
    else:
        return str(content)


def is_user_interruption(content):
    """Check if content contains user interruption."""
    text = extract_text_content(content)
    return ("[Request interrupted by user]" in text or 
            "[Request interrupted by user for tool use]" in text)


def calculate_session_stats(lines):
    """Calculate session statistics."""
    stats = {
        'total_messages': 0,
        'user_messages': 0,
        'assistant_messages': 0,
        'file_operations': 0,
        'start_time': None,
        'end_time': None,
        'session_duration_seconds': 0,
        'estimated_input_tokens': 0,
        'estimated_output_tokens': 0,
        'estimated_total_tokens': 0,
        'files_modified': set(),
        'programming_languages': set()
    }
    
    for line in lines:
        try:
            data = json.loads(line.strip())
            
            if data.get('isMeta') or 'message' not in data:
                continue
                
            message = data['message']
            content = message.get('content', '')
            
            if not content:
                continue
                
            # Track timestamps
            timestamp = data.get('timestamp')
            if timestamp:
                if stats['start_time'] is None:
                    stats['start_time'] = timestamp
                stats['end_time'] = timestamp
            
            # Count messages and estimate tokens
            role = message.get('role', '')
            message_tokens = len(extract_text_content(content)) // 3
            
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        if part.get('type') == 'tool_use':
                            tool_input = part.get('input', {})
                            message_tokens += len(json.dumps(tool_input)) // 3
                        elif part.get('type') == 'tool_result':
                            result_content = str(part.get('content', ''))
                            message_tokens += len(result_content) // 3
            
            if role == 'user':
                stats['user_messages'] += 1
                stats['estimated_input_tokens'] += message_tokens
            elif role == 'assistant':
                stats['assistant_messages'] += 1
                stats['estimated_output_tokens'] += message_tokens
                
            stats['total_messages'] += 1
            stats['estimated_total_tokens'] += int(message_tokens * 1.2)
            
            # Track file operations
            file_ops = extract_file_operations(content)
            for op in file_ops:
                stats['file_operations'] += 1
                if op['file_name']:
                    stats['files_modified'].add(op['file_name'])
                    stats['programming_languages'].add(op.get('language', 'text'))
                    
        except:
            continue
    
    # Calculate duration
    if stats['start_time'] and stats['end_time']:
        try:
            start_dt = datetime.fromisoformat(stats['start_time'].replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(stats['end_time'].replace('Z', '+00:00'))
            stats['session_duration_seconds'] = int((end_dt - start_dt).total_seconds())
        except:
            pass
    
    # Convert sets to lists for JSON serialization
    stats['files_modified'] = list(stats['files_modified'])
    stats['programming_languages'] = list(stats['programming_languages'])
    
    return stats


def convert_log_to_json(jsonl_file, output_file=None, include_content=True):
    """Convert JSONL log file to simplified JSON format."""
    input_path = Path(jsonl_file)
    
    if not input_path.exists():
        print(f"Error: File {jsonl_file} not found")
        return False
    
    if output_file is None:
        output_file = input_path.with_suffix('.json')
    
    output_path = Path(output_file)
    
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Calculate session statistics
        stats = calculate_session_stats(lines)
        
        # Process messages
        messages = []
        timeline = []
        file_operations = []
        message_id = 0
        
        for line_num, line in enumerate(lines):
            try:
                data = json.loads(line.strip())
                
                # Skip meta messages
                if data.get('isMeta') or 'message' not in data:
                    continue
                
                message = data['message']
                role = message.get('role', 'unknown')
                content = message.get('content', '')
                
                if not content:
                    continue
                
                message_id += 1
                timestamp = data.get('timestamp')
                is_sidechain = data.get('isSidechain', False)
                
                # Extract file operations
                file_ops = extract_file_operations(content)
                
                # Create message object
                msg = {
                    'id': message_id,
                    'line_number': line_num + 1,
                    'timestamp': timestamp,
                    'role': role,
                    'is_sidechain': is_sidechain,
                    'is_interruption': is_user_interruption(content),
                    'has_file_operations': len(file_ops) > 0,
                    'file_operation_count': len(file_ops),
                    'content_length': len(extract_text_content(content)),
                    'estimated_tokens': len(extract_text_content(content)) // 3
                }
                
                # Optionally include full content
                if include_content:
                    msg['content'] = extract_text_content(content)
                    msg['content_preview'] = extract_text_content(content)[:200] + ('...' if len(extract_text_content(content)) > 200 else '')
                else:
                    msg['content_preview'] = extract_text_content(content)[:200] + ('...' if len(extract_text_content(content)) > 200 else '')
                
                messages.append(msg)
                
                # Add to timeline
                timeline_event = {
                    'message_id': message_id,
                    'timestamp': timestamp,
                    'type': 'message',
                    'role': role,
                    'is_sidechain': is_sidechain,
                    'summary': msg['content_preview']
                }
                timeline.append(timeline_event)
                
                # Process file operations
                for op in file_ops:
                    op['message_id'] = message_id
                    op['timestamp'] = timestamp
                    op['is_sidechain'] = is_sidechain
                    file_operations.append(op)
                    
                    # Add file operation to timeline
                    timeline.append({
                        'message_id': message_id,
                        'timestamp': timestamp,
                        'type': 'file_operation',
                        'operation_type': op['type'],
                        'file_name': op['file_name'],
                        'summary': f"{op['type'].title()}: {op['file_name']}"
                    })
                
            except Exception as e:
                print(f"Error processing line {line_num + 1}: {e}")
                continue
        
        # Create final JSON structure
        result = {
            'metadata': {
                'source_file': input_path.name,
                'generated_at': datetime.now().isoformat(),
                'total_lines_processed': len(lines),
                'include_full_content': include_content
            },
            'session_stats': stats,
            'messages': messages,
            'file_operations': file_operations,
            'timeline': sorted(timeline, key=lambda x: x.get('timestamp', '')),
            'summary': {
                'message_count': len(messages),
                'file_operation_count': len(file_operations),
                'unique_files': len(stats['files_modified']),
                'programming_languages': stats['programming_languages'],
                'session_duration_formatted': format_duration(stats['session_duration_seconds'])
            }
        }
        
        # Write JSON output
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"Successfully converted {len(messages)} messages to {output_path}")
        print(f"- {len(file_operations)} file operations")
        print(f"- {len(stats['files_modified'])} unique files modified")
        print(f"- {stats['session_duration_seconds']} seconds duration")
        
        return True
        
    except Exception as e:
        print(f"Error processing file: {e}")
        return False


def format_duration(seconds):
    """Format duration in seconds to human readable format."""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        remaining_seconds = seconds % 60
        return f"{hours}h {minutes}m {remaining_seconds}s"


def main():
    parser = argparse.ArgumentParser(description='Convert Claude JSONL logs to JSON for visualization')
    parser.add_argument('input_file', help='Path to the JSONL log file')
    parser.add_argument('-o', '--output', help='Output JSON file (default: input_file.json)')
    parser.add_argument('--no-content', action='store_true', help='Exclude full message content (only include previews)')
    
    args = parser.parse_args()
    
    include_content = not args.no_content
    success = convert_log_to_json(args.input_file, args.output, include_content)
    
    if success:
        print("\nTip: Use process_json_with_secrets.py to apply secret replacements for safe sharing")
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()