#!/usr/bin/env python3
"""
Load problem decomposition data from YAML into PostgreSQL issues table - Simplified version
"""

import yaml
import asyncio
import uuid
from typing import Dict, List, Any
from datetime import datetime
import sys
import os
import asyncpg
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")

async def get_db_connection():
    """Get a database connection"""
    return await asyncpg.connect(DATABASE_URL)

def load_yaml_data(file_path: str) -> Dict[str, Any]:
    """Load YAML data from file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def transform_atomic_problem(problem_data: Dict[str, Any]) -> Dict[str, Any]:
    """Transform atomic problem data to database format"""
    
    # Extract keywords from detection logic
    keywords = []
    if 'detection_logic' in problem_data:
        detection_logic = problem_data['detection_logic']
        if 'keywords' in detection_logic:
            keywords = detection_logic['keywords']
    
    # Create description from problem data
    description = problem_data.get('description', '')
    if 'check_method' in problem_data:
        check_method = problem_data['check_method']
        description += f"\n\nCheck method: {check_method.get('type', 'unknown')}"
        if 'api' in check_method:
            description += f" via {check_method['api']}"
    
    # Determine severity based on metadata
    severity = 'Medium'  # default (capitalized)
    if 'metadata' in problem_data:
        impact = problem_data['metadata'].get('impact', 'medium')
        if impact in ['critical']:
            severity = 'Critical'
        elif impact in ['high']:
            severity = 'High'
        elif impact in ['low', 'informational']:
            severity = 'Low'
    
    # Determine category
    category = problem_data.get('category', 'general')
    
    # Create diagnostic questions
    diagnostic_questions = []
    if 'required_fields' in problem_data:
        for field in problem_data['required_fields']:
            diagnostic_questions.append({
                "question": f"Please provide the {field}",
                "required": True,
                "field": field
            })
    
    # Create tools list
    tools = []
    if 'check_method' in problem_data and 'api' in problem_data['check_method']:
        tools.append({
            "name": problem_data['check_method']['api'],
            "type": "api_check",
            "description": f"Check {problem_data['code']}"
        })
    
    return {
        'issue_id': str(uuid.uuid4()),
        'title': problem_data['name'],
        'description': description,
        'category': category,
        'severity': severity,
        'keywords': keywords,
        'diagnostic_questions': diagnostic_questions,
        'tools': tools,
        'source_reference': f"{problem_data['id']}: {problem_data['code']}"
    }

def transform_solution(solution_data: Dict[str, Any]) -> Dict[str, Any]:
    """Transform solution data to database format"""
    
    # Create description from solution steps
    description = ""
    if 'steps' in solution_data:
        for step in solution_data['steps']:
            description += f"Step {step['step']}: {step['action']}\n"
            if 'details' in step:
                description += f"Details: {step['details']}\n"
            if 'warning' in step:
                description += f"Warning: {step['warning']}\n"
    
    if 'verification' in solution_data:
        description += f"\nVerification: {solution_data['verification']}"
    
    # Determine category based on atomic problem
    category = 'solution'
    atomic_problem = solution_data.get('atomic_problem', '')
    if 'FORMULA' in atomic_problem:
        category = 'formula_solution'
    elif 'DATA' in atomic_problem:
        category = 'data_solution'
    elif 'CONFIG' in atomic_problem:
        category = 'config_solution'
    
    # Extract keywords from solution
    keywords = []
    if 'steps' in solution_data:
        for step in solution_data['steps']:
            action = step.get('action', '').lower()
            # Extract meaningful keywords
            if 'công thức' in action:
                keywords.append('công thức')
            if 'kho' in action:
                keywords.append('kho')
            if 'đồng bộ' in action:
                keywords.append('đồng bộ')
            if 'tính giá' in action:
                keywords.append('tính giá')
    
    return {
        'issue_id': str(uuid.uuid4()),
        'title': solution_data['name'],
        'description': description,
        'category': category,
        'severity': 'Medium',
        'keywords': keywords,
        'diagnostic_questions': [],
        'tools': [],
        'source_reference': solution_data['id']
    }

async def insert_issues_batch(connection, records: List[Dict[str, Any]]) -> None:
    """Insert multiple issues into database"""
    
    for i, record in enumerate(records):
        try:
            # Use dummy embedding for now (1536 dimensions with 0.1 values)
            # Create slight variations to make them unique
            base_value = 0.1 + (i * 0.01)
            dummy_embedding = [base_value] * 1536
            
            # Convert embedding to string format for PostgreSQL vector type
            embedding_str = f"[{','.join(map(str, dummy_embedding))}]"
            
            # Convert JSON fields to strings
            symptoms_json = "{}"
            diagnostic_questions_json = json.dumps(record['diagnostic_questions']) if record['diagnostic_questions'] else "[]"
            tools_json = json.dumps(record['tools']) if record['tools'] else "[]"
            keywords_json = record['keywords'] if record['keywords'] else []
            
            # Insert into database
            query = """
            INSERT INTO issues (
                issue_id, 
                title, 
                description, 
                category, 
                severity, 
                symptoms, 
                diagnostic_questions, 
                tools, 
                keywords, 
                embedding,
                created_at,
                updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::vector, NOW(), NOW())
            """
            
            await connection.execute(
                query,
                record['issue_id'],
                record['title'],
                record['description'],
                record['category'],
                record['severity'],
                symptoms_json,
                diagnostic_questions_json,
                tools_json,
                keywords_json,
                embedding_str
            )
            
            print(f"✅ Inserted: {record['title']}")
            
        except Exception as e:
            print(f"❌ Failed to insert {record['title']}: {e}")

async def load_problem_decomposition_data(yaml_file_path: str) -> None:
    """Load problem decomposition data from YAML into database"""
    
    print("🚀 Starting to load problem decomposition data...")
    
    # Load YAML data
    try:
        yaml_data = load_yaml_data(yaml_file_path)
        print(f"📄 Loaded YAML file with metadata version {yaml_data.get('metadata', {}).get('version', 'unknown')}")
    except Exception as e:
        print(f"❌ Failed to load YAML file: {e}")
        return
    
    # Transform atomic problems
    atomic_problems = yaml_data.get('atomic_problems', {})
    records = []
    
    print(f"🔧 Processing {len(atomic_problems)} atomic problems...")
    
    for problem_id, problem_data in atomic_problems.items():
        try:
            # Transform to database format
            transformed = transform_atomic_problem(problem_data)
            records.append(transformed)
            
        except Exception as e:
            print(f"⚠️  Warning: Failed to transform atomic problem {problem_id}: {e}")
    
    # Transform solutions
    solutions = yaml_data.get('solutions', {})
    print(f"💡 Processing {len(solutions)} solutions...")
    
    for solution_id, solution_data in solutions.items():
        try:
            # Transform to database format
            transformed = transform_solution(solution_data)
            records.append(transformed)
            
        except Exception as e:
            print(f"⚠️  Warning: Failed to transform solution {solution_id}: {e}")
    
    print(f"📊 Total records to insert: {len(records)}")
    
    # Insert into database
    if records:
        try:
            connection = await get_db_connection()
            await insert_issues_batch(connection, records)
            await connection.close()
            
            print(f"✅ Successfully loaded {len(records)} records into database")
            
        except Exception as e:
            print(f"❌ Failed to insert records into database: {e}")
    else:
        print("⚠️  No records to insert")

async def main():
    """Main function"""
    yaml_file_path = "/Users/tuyenpham712/Work/support-multi-agent/resource/problem_decomposition_system.yaml"
    
    await load_problem_decomposition_data(yaml_file_path)

if __name__ == "__main__":
    asyncio.run(main())