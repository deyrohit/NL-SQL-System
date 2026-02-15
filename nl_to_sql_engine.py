import os
import re
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

class DatabaseSchema:
    """Stores and manages database schema information"""
    
    SCHEMA_INFO = """
    Database Schema:
    
    1. vehicle_cards:
       - card_id (INTEGER, PRIMARY KEY)
       - vehicle_type (VARCHAR) - values: 'Car', 'Truck', 'SUV', 'Van', 'Motorcycle'
       - manufacturer (VARCHAR) - e.g., 'Toyota', 'Honda', 'Maruti', 'Hyundai'
       - model (VARCHAR) - e.g., 'Fortuner', 'Camry', 'Verna', 'Baleno'
       - manufacture_year (INTEGER)
       - created_at (DATE)
    
    2. damage_detections:
       - damage_id (INTEGER, PRIMARY KEY)
       - card_id (INTEGER, FOREIGN KEY → vehicle_cards)
       - panel_name (VARCHAR) - e.g., 'front_bumper', 'rear_bumper', 'door_left', 'door_right', 'bonnet'
       - damage_type (VARCHAR) - values: 'scratch', 'dent', 'crack', 'broken', 'paint_damage'
       - severity (VARCHAR) - values: 'minor', 'moderate', 'severe', 'critical'
       - confidence (DECIMAL 0-1) - AI detection confidence
       - detected_at (DATE)
    
    3. repairs:
       - repair_id (INTEGER, PRIMARY KEY)
       - card_id (INTEGER, FOREIGN KEY → vehicle_cards)
       - panel_name (VARCHAR) - same values as damage_detections.panel_name
       - repair_action (VARCHAR) - values: 'paint', 'replace', 'repair', 'polish', 'dent_removal'
       - repair_cost (DECIMAL)
       - approved (BOOLEAN)
       - created_at (DATE)
    
    4. quotes:
       - quote_id (INTEGER, PRIMARY KEY)
       - card_id (INTEGER, FOREIGN KEY → vehicle_cards)
       - total_estimated_cost (DECIMAL)
       - currency (VARCHAR) - typically 'INR'
       - generated_at (DATE)
    
    Important Notes:
    - Panel names use underscores: 'front_bumper', 'rear_bumper', not 'front bumper'
    - For informal terms like "back bumper", use LIKE '%rear%bumper%'
    - For "front panel" or "front side", search for panel names containing 'front'
    - Current date is {current_date}
    - For time ranges: "last 30 days" = WHERE created_at >= CURRENT_DATE - 30
    - For "this month" = WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)
    """
    
    @classmethod
    def get_schema_prompt(cls) -> str:
        return cls.SCHEMA_INFO.format(current_date=datetime.now().strftime('%Y-%m-%d'))

class SQLValidator:
    ALLOWED_KEYWORDS = {
        'SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
        'GROUP BY', 'HAVING', 'ORDER BY', 'LIMIT', 'OFFSET', 'AS', 'ON',
        'AND', 'OR', 'NOT', 'IN', 'LIKE', 'BETWEEN', 'IS', 'NULL',
        'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'STDDEV', 'VARIANCE',
        'DISTINCT', 'ASC', 'DESC', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
        'CAST', 'EXTRACT', 'DATE_TRUNC', 'CURRENT_DATE', 'INTERVAL'
    }
    
    FORBIDDEN_KEYWORDS = {
        'DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE', 'TRUNCATE',
        'GRANT', 'REVOKE', 'EXECUTE', 'EXEC', 'CALL', ';--', 'UNION',
        'INTO OUTFILE', 'LOAD_FILE', 'xp_cmdshell'
    }
    
    @classmethod
    def validate_query(cls, query: str) -> Tuple[bool, Optional[str]]:
        query_upper = query.upper()
        
        # Check for forbidden keywords
        for keyword in cls.FORBIDDEN_KEYWORDS:
            if keyword in query_upper:
                return False, f"Forbidden operation detected: {keyword}"
        
        # Must start with SELECT
        if not query_upper.strip().startswith('SELECT'):
            return False, "Query must start with SELECT"
        
        # Check for multiple statements
        if query.count(';') > 1:
            return False, "Multiple statements not allowed"
        
        # Basic SQL injection patterns
        injection_patterns = [
            r';\s*DROP',
            r';\s*DELETE',
            r'--\s',
            r'/\*.*\*/',
            r'@@version',
            r'benchmark\s*\(',
            r'sleep\s*\(',
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                return False, f"Potential SQL injection detected: {pattern}"
        
        return True, None
    
    @classmethod
    def sanitize_limit(cls, query: str, max_limit: int = 1000) -> str:
        """Add or enforce LIMIT clause"""
        if 'LIMIT' not in query.upper():
            query = query.rstrip(';') + f' LIMIT {max_limit};'
        return query


class NLToSQLConverter:
    """Converts natural language queries to SQL using Groq API"""
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        self.client = Groq(api_key=api_key)
        self.model = model
        self.schema = DatabaseSchema()
        self.validator = SQLValidator()
    
    def generate_sql(self, natural_language_query: str) -> Dict:
        system_prompt = f"""You are a SQL expert for the ClearQuote vehicle damage database.

{self.schema.get_schema_prompt()}

Your task:
1. Convert natural language queries to valid PostgreSQL SELECT queries
2. Handle ambiguous terms (e.g., "back bumper" → use LIKE '%rear%bumper%')
3. Handle missing time ranges (assume last 30 days if not specified)
4. Use proper JOINs when querying multiple tables
5. Return ONLY valid SQL, no explanations in the SQL itself

CRITICAL RULES:
- ONLY generate SELECT queries
- NO DROP, DELETE, INSERT, UPDATE, or other destructive operations
- Use parameterized patterns for safety
- Always include LIMIT clause (max 1000)
- For panel names, use LOWER() and LIKE for fuzzy matching
- For time ranges without specifics, use last 30 days

Response format:
Return a JSON object with:
{{
  "sql": "the SQL query",
  "explanation": "brief explanation of the query logic",
  "assumptions": ["list of assumptions made"],
  "confidence": 0.0-1.0
}}
"""
        
        user_prompt = f"""Convert this natural language query to SQL:
"{natural_language_query}"

Remember to handle ambiguous terms and add appropriate time filters if missing.
Return ONLY the JSON response, no other text."""
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                model=self.model,
                temperature=0.1,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            # Extract response
            response_text = chat_completion.choices[0].message.content
            
            # Parse JSON from response
            response_json = json.loads(response_text)
            
            # Validate the SQL
            sql_query = response_json.get('sql', '')
            is_valid, error = self.validator.validate_query(sql_query)
            
            if not is_valid:
                return {
                    'success': False,
                    'error': f"Generated SQL failed validation: {error}",
                    'sql': sql_query
                }
            
            # Add limit if needed
            sql_query = self.validator.sanitize_limit(sql_query)
            response_json['sql'] = sql_query
            response_json['success'] = True
            
            return response_json
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Failed to generate SQL: {str(e)}",
                'sql': None
            }


class DatabaseExecutor:
    def __init__(self, db_config: Dict):
        self.db_config = db_config
    
    def execute_query(self, sql: str) -> Dict:
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute(sql)
            results = cursor.fetchall()
            
            # Convert to list of dicts
            data = [dict(row) for row in results]
            
            cursor.close()
            conn.close()
            
            return {
                'success': True,
                'data': data,
                'row_count': len(data),
                'error': None
            }
            
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'row_count': 0,
                'error': str(e)
            }


class AnswerGenerator:
    def __init__(self, api_key: str, model: str = "llama-3.1-8b-instant"):
        self.client = Groq(api_key=api_key)
        self.model = model
    
    def generate_answer(self, 
                       natural_query: str, 
                       sql_query: str, 
                       results: List[Dict]) -> str:
        
        if not results:
            return "No results found for your query."
        
        system_prompt = """You are a helpful assistant that converts database query results into clear, natural language answers.

Rules:
1. Be concise and direct
2. Include specific numbers and data points
3. Format numbers appropriately (e.g., currency with 2 decimals)
4. If there are multiple results, summarize key insights
5. Avoid technical jargon
6. Be trustworthy - don't add information not in the data"""
        
        results_str = json.dumps(results[:10], indent=2, default=str) 
        
        user_prompt = f"""The user asked: "{natural_query}"
SQL Query executed: {sql_query}

Results ({len(results)} rows):
{results_str}

Generate a clear, user-friendly answer to their question based on these results."""
        
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                model=self.model,
                temperature=0.3,
                max_tokens=1000
            )
            
            return chat_completion.choices[0].message.content
            
        except Exception as e:
            # Fallback to simple formatting
            return self._format_results_simple(natural_query, results)
    
    def _format_results_simple(self, query: str, results: List[Dict]) -> str:
        if len(results) == 1 and len(results[0]) == 1:
            _, value = list(results[0].items())[0]
            return f"Result: {value}"
        
        output = f"Found {len(results)} results:\n\n"
        for i, row in enumerate(results[:5], 1):
            output += f"{i}. " + ", ".join([f"{k}: {v}" for k, v in row.items()]) + "\n"
        
        if len(results) > 5:
            output += f"\n... and {len(results) - 5} more results"
        return output


class ClearQuoteNLSQL:
    def __init__(self, api_key: str, db_config: Dict, model: str = "llama-3.1-8b-instant"):
        self.converter = NLToSQLConverter(api_key, model)
        self.executor = DatabaseExecutor(db_config)
        self.answer_gen = AnswerGenerator(api_key, model)
    
    def process_query(self, natural_language_query: str) -> Dict:
        
        # Step 1: Convert to SQL
        sql_result = self.converter.generate_sql(natural_language_query)
        if not sql_result.get('success'):
            return {
                'success': False,
                'error': sql_result.get('error'),
                'stage': 'sql_generation'
            }
        sql_query = sql_result['sql']
        
        # Step 2: Execute SQL
        exec_result = self.executor.execute_query(sql_query)
        if not exec_result.get('success'):
            return {
                'success': False,
                'error': exec_result.get('error'),
                'sql': sql_query,
                'stage': 'execution'
            }
        
        # Step 3: Generate natural language answer
        answer = self.answer_gen.generate_answer(
            natural_language_query,
            sql_query,
            exec_result['data'],
        )
        
        return {
            'success': True,
            'query': natural_language_query,
            'sql': sql_query,
            'assumptions': sql_result.get('assumptions', []),
            'confidence': sql_result.get('confidence', 0.0),
            'row_count': exec_result['row_count'],
            'data': exec_result['data'],
            'answer': answer,
            'stage': 'complete'
        }


def main():
    API_KEY = os.getenv('GROQ_API_KEY')
    
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'database': os.getenv('DB_NAME', 'clearquote'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD')
    }
    
    MODEL = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')

    system = ClearQuoteNLSQL(API_KEY, DB_CONFIG, model=MODEL)
    
    # Example queries
    test_queries = [
        "How many damages i have on my roof combining all the vehicles",
        # "How many vehicles had severe damages on the front panel this month?",
        # "Which car models have the highest repair cost variance?",
        # "Show me all Toyota vehicles with damages",
        # "What's the total cost of approved repairs?"
    ]
    
    print("ClearQuote NL→SQL System")
    print("=" * 60)
    print(f"Using model: {MODEL}")
    print(f"Database: {DB_CONFIG['database']} @ {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print("=" * 60)
    
    for query in test_queries:
        print(f"\n Query: {query}")
        print("-" * 60)
        
        result = system.process_query(query)
        
        if result['success']:
            print(f"Success!")
            print(f"\nSQL Generated:\n{result['sql']}")
            print(f"\nFound {result['row_count']} results")
            print(f"\nAnswer:\n{result['answer']}")
            
            if result.get('assumptions'):
                print(f"\n Assumptions: {', '.join(result['assumptions'])}")
        else:
            print(f"✗ Error at {result['stage']}: {result['error']}")
        print("\n" + "=" * 60)

if __name__ == "__main__":
    main()