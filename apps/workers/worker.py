import os
import time
import logging
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set up Sentry with enhanced logging integration
sentry_logging = LoggingIntegration(
    level=logging.INFO,        # Capture info and above as breadcrumbs
    event_level=logging.ERROR  # Send errors as events
)

# Initialize Sentry
sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    traces_sample_rate=0.2,
    integrations=[sentry_logging],
)

# Database connection string
DATABASE_URL = os.environ.get("DATABASE_URL")

def connect_to_db():
    """Establish a connection to the database."""
    try:
        connection = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        connection.autocommit = True
        logger.info("Connected to the database successfully")
        return connection
    except Exception as e:
        logger.error(f"Error connecting to the database: {e}")
        return None

def process_tasks():
    """Process any pending tasks in the database."""
    connection = connect_to_db()
    if not connection:
        logger.error("Failed to connect to database, skipping processing")
        return
    
    try:
        cursor = connection.cursor()
        
        # Query for pending tasks
        cursor.execute("""
            SELECT * FROM tasks 
            WHERE status = 'pending' 
            ORDER BY created_at ASC 
            LIMIT 5
        """)
        tasks = cursor.fetchall()
        
        for task in tasks:
            logger.info(f"Processing task {task['id']}")
            
            # Update task status to 'processing'
            cursor.execute("""
                UPDATE tasks 
                SET status = 'processing', updated_at = NOW() 
                WHERE id = %s
            """, (task['id'],))
            
            # Process the task (placeholder for actual processing logic)
            try:
                # Simulate task processing
                time.sleep(2)
                
                # Update task as complete
                cursor.execute("""
                    UPDATE tasks 
                    SET status = 'completed', updated_at = NOW() 
                    WHERE id = %s
                """, (task['id'],))
                logger.info(f"Task {task['id']} completed successfully")
            except Exception as e:
                logger.error(f"Error processing task {task['id']}: {e}")
                cursor.execute("""
                    UPDATE tasks 
                    SET status = 'failed', error = %s, updated_at = NOW() 
                    WHERE id = %s
                """, (str(e), task['id']))
    except Exception as e:
        logger.error(f"Error in process_tasks: {e}")
    finally:
        connection.close()

def main():
    """Main worker loop."""
    logger.info("Worker started")
    while True:
        try:
            process_tasks()
        except Exception as e:
            logger.error(f"Unhandled exception in worker loop: {e}")
        
        # Sleep for a few seconds before next check
        time.sleep(5)

if __name__ == "__main__":
    main() 