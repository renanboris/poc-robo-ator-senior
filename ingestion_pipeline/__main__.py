"""CLI entrypoint for the Web Knowledge Ingestion Pipeline."""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pinecone import Pinecone

from ingestion_pipeline.config import PipelineConfig
from ingestion_pipeline.pipeline import IngestionPipeline

# Load environment variables
load_dotenv()


def validate_env_vars() -> bool:
    """Validate required environment variables.
    
    Returns:
        True if all required vars are present, False otherwise
    """
    required_vars = [
        "OPENAI_API_KEY",
        "PINECONE_API_KEY",
        "PINECONE_INDEX_NAME"
    ]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print("ERROR: Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease configure these variables in your .env file")
        return False

    return True


def list_namespaces() -> int:
    """List all Pinecone namespaces with vector counts.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        api_key = os.getenv("PINECONE_API_KEY")
        index_name = os.getenv("PINECONE_INDEX_NAME")

        pc = Pinecone(api_key=api_key)
        index = pc.Index(index_name)

        # Get index stats
        stats = index.describe_index_stats()

        print("\nPinecone Namespaces")
        print("=" * 60)
        print(f"Index: {index_name}")
        print(f"Total vectors: {stats.get('total_vector_count', 0):,}")
        print("\nNamespaces:")
        print("-" * 60)

        namespaces = stats.get('namespaces', {})

        if not namespaces:
            print("  (no namespaces found)")
        else:
            for namespace, info in sorted(namespaces.items()):
                vector_count = info.get('vector_count', 0)
                print(f"  {namespace:<30} {vector_count:>10,} vectors")

        print("=" * 60)

        return 0

    except Exception as e:
        print(f"ERROR: Failed to list namespaces: {e}")
        return 1


def delete_namespace(namespace: str, dry_run: bool = False) -> int:
    """Delete all vectors in the specified namespace.
    
    Args:
        namespace: Namespace to delete
        dry_run: If True, simulate without making changes
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        api_key = os.getenv("PINECONE_API_KEY")
        index_name = os.getenv("PINECONE_INDEX_NAME")

        pc = Pinecone(api_key=api_key)
        index = pc.Index(index_name)

        # Get namespace stats
        stats = index.describe_index_stats()
        namespaces = stats.get('namespaces', {})

        if namespace not in namespaces:
            print(f"ERROR: Namespace '{namespace}' not found")
            print(f"\nAvailable namespaces: {', '.join(namespaces.keys())}")
            return 1

        vector_count = namespaces[namespace].get('vector_count', 0)

        print(f"\nNamespace: {namespace}")
        print(f"Vectors: {vector_count:,}")

        if dry_run:
            print("\n[DRY-RUN] Would delete all vectors in this namespace")
            return 0

        # Confirmation prompt
        print("\nWARNING: This will permanently delete all vectors in this namespace!")
        response = input("Type 'yes' to confirm deletion: ")

        if response.lower() != 'yes':
            print("Deletion cancelled")
            return 0

        # Delete all vectors in namespace
        print(f"\nDeleting namespace '{namespace}'...")
        index.delete(delete_all=True, namespace=namespace)

        print(f"✓ Successfully deleted namespace '{namespace}'")

        return 0

    except Exception as e:
        print(f"ERROR: Failed to delete namespace: {e}")
        return 1


def run_pipeline(args) -> int:
    """Execute the ingestion pipeline.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Load configuration from environment
        config = PipelineConfig(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            pinecone_api_key=os.getenv("PINECONE_API_KEY"),
            pinecone_index_name=os.getenv("PINECONE_INDEX_NAME"),
            firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY"),
            extraction_backend=args.backend,
            chunk_size=800,
            chunk_overlap=100,
            embedding_model="text-embedding-3-large",
            embedding_dimensions=3072,
            batch_size=100,
            max_retries=3,
            retry_delays=[1, 2, 4],
            cache_file=".ingestion_cache.json"
        )

        # Instantiate pipeline
        pipeline = IngestionPipeline(config)

        # Print header
        print("\nWeb Knowledge Ingestion Pipeline")
        print("=" * 60)
        print(f"Sitemap URL: {args.sitemap_url}")
        print(f"Backend: {args.backend}")
        print(f"Incremental: {args.incremental}")
        print(f"Dry-run: {args.dry_run}")
        if args.module:
            print(f"Module filter: {args.module}")
        print("=" * 60)

        if args.dry_run:
            print("\n[DRY-RUN MODE] Simulating operations without upserting to Pinecone")
            print("Note: Dry-run mode is not fully implemented yet")
            return 0

        # Execute pipeline
        print("\nStarting pipeline execution...\n")
        report = pipeline.run(
            sitemap_url=args.sitemap_url,
            incremental=args.incremental,
            module_filter=args.module
        )

        # Print summary report
        print("\n")
        report.print_summary()

        return 0

    except Exception as e:
        print(f"\nERROR: Pipeline execution failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Web Knowledge Ingestion Pipeline for Senior Training OS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml
  
  # Process only HCM module (recommended for testing)
  python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --module hcm
  
  # Incremental mode (skip unchanged URLs)
  python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --incremental
  
  # Dry-run mode (simulate without upserting)
  python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --dry-run
  
  # List namespaces
  python -m ingestion_pipeline --list-namespaces
  
  # Delete namespace (with confirmation)
  python -m ingestion_pipeline --delete-namespace hcm
  
  # Specify extraction backend
  python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --backend firecrawl
        """
    )

    parser.add_argument(
        "sitemap_url",
        nargs="?",
        help="URL of the sitemap.xml to process"
    )

    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Skip URLs with unchanged content (uses local cache)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate operations without making changes to Pinecone"
    )

    parser.add_argument(
        "--backend",
        choices=["crawl4ai", "firecrawl"],
        default="crawl4ai",
        help="Content extraction backend (default: crawl4ai)"
    )

    parser.add_argument(
        "--list-namespaces",
        action="store_true",
        help="List all Pinecone namespaces with vector counts"
    )

    parser.add_argument(
        "--delete-namespace",
        metavar="NAMESPACE",
        help="Delete all vectors in the specified namespace"
    )

    parser.add_argument(
        "--module",
        metavar="MODULE",
        help="Process only URLs from a specific module (e.g., 'hcm', 'financeiro'). Filters by nivel_2 in URL path."
    )

    args = parser.parse_args()

    # Validate arguments
    if not any([args.sitemap_url, args.list_namespaces, args.delete_namespace]):
        parser.error("Must provide sitemap_url or use --list-namespaces or --delete-namespace")

    # Validate environment variables
    if not validate_env_vars():
        return 1

    # Execute command
    if args.list_namespaces:
        return list_namespaces()

    elif args.delete_namespace:
        return delete_namespace(args.delete_namespace, args.dry_run)

    else:
        return run_pipeline(args)


if __name__ == "__main__":
    sys.exit(main())
