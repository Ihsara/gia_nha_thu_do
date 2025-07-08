import duckdb
import json
import os
from datetime import datetime
from pathlib import Path

def get_db_connection():
    """Get database connection"""
    return duckdb.connect("data/real_estate.duckdb")

def export_table_sample(conn, table_name, sample_size=10):
    """Export sample data from a table"""
    try:
        # Get sample data
        query = f"SELECT * FROM {table_name} LIMIT {sample_size}"
        result = conn.execute(query).fetchall()
        
        # Get column names
        column_query = f"DESCRIBE {table_name}"
        columns = conn.execute(column_query).fetchall()
        column_names = [col[0] for col in columns]
        
        # Convert to list of dictionaries
        sample_data = []
        for row in result:
            row_dict = {}
            for i, value in enumerate(row):
                # Convert any non-serializable types to strings
                if isinstance(value, (bytes, bytearray)):
                    row_dict[column_names[i]] = str(value)
                else:
                    row_dict[column_names[i]] = value
            sample_data.append(row_dict)
        
        return {
            "table_name": table_name,
            "sample_size": len(sample_data),
            "total_columns": len(column_names),
            "columns": column_names,
            "sample_data": sample_data,
            "exported_at": datetime.now().isoformat()
        }
    
    except Exception as e:
        return {
            "table_name": table_name,
            "error": str(e),
            "exported_at": datetime.now().isoformat()
        }

def main():
    """Main export function"""
    # Ensure output directory exists
    Path("output/sample").mkdir(parents=True, exist_ok=True)
    
    # Connect to database
    conn = get_db_connection()
    
    # Get all tables
    tables_query = "SHOW TABLES"
    tables = conn.execute(tables_query).fetchall()
    table_names = [table[0] for table in tables]
    
    print(f"Found {len(table_names)} tables:")
    for table in table_names:
        print(f"  - {table}")
    
    # Generate timestamp for this export session
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Export each table
    for table_name in table_names:
        print(f"\nExporting sample from {table_name}...")
        
        # Create table directory
        table_dir = Path(f"output/sample/{table_name}")
        table_dir.mkdir(exist_ok=True)
        
        # Export sample data
        sample_data = export_table_sample(conn, table_name)
        
        # Save to JSON file
        filename = f"{timestamp}.json"
        filepath = table_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(sample_data, f, indent=2, ensure_ascii=False, default=str)
        
        if "error" not in sample_data:
            print(f"  ✓ Exported {sample_data['sample_size']} rows to {filepath}")
        else:
            print(f"  ✗ Error exporting {table_name}: {sample_data['error']}")
    
    # Create summary file
    summary = {
        "export_session": timestamp,
        "total_tables": len(table_names),
        "tables_exported": table_names,
        "export_directory": "output/sample/",
        "notes": "Each table directory contains timestamped JSON files with sample data"
    }
    
    summary_file = Path(f"output/sample/export_summary_{timestamp}.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Export complete! Summary saved to {summary_file}")
    print(f"✓ All sample data saved in output/sample/ directory")
    
    conn.close()

if __name__ == "__main__":
    main()
