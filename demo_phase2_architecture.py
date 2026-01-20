#!/usr/bin/env python3
"""
Phase 2 Architecture Demonstration

Shows how to use the new multi-object architecture:
- ObjectRegistry for object type configurations
- Fetchers for data retrieval
- ReportRegistry for report definitions
"""
import sys
from src.config import load_config
from src.hubspot_client import HubSpotClient
from src.core import ObjectRegistry
from src.reporting.report_registry import ReportRegistry
from src.fetchers import DealsFetcher, ContactsFetcher, CompaniesFetcher


def print_section(title: str):
    """Print section header"""
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demo_object_registry():
    """Demonstrate ObjectRegistry usage"""
    print_section("1. Object Registry - Centralized Object Type Configuration")

    registry = ObjectRegistry()

    print(f"\nLoaded {len(registry.list_types())} object types:")
    for object_type in registry.list_types():
        config = registry.get(object_type)
        print(f"\n  📦 {config.display_name} ({object_type})")
        print(f"     - Properties: {len(config.properties)} fields")
        print(f"     - Has History: {config.has_history}")
        print(f"     - Has Stages: {config.has_stages}")
        print(f"     - Supports Associations: {config.supports_associations}")

    print("\n✅ Object types are now JSON-configurable!")
    print("   New object types can be added by editing config/object_types.json")


def demo_fetchers():
    """Demonstrate Fetcher architecture"""
    print_section("2. Fetchers - Generic Data Retrieval for All Object Types")

    # Load config and initialize client
    config = load_config()
    client = HubSpotClient(config)
    registry = ObjectRegistry()

    # Show fetcher for each object type
    fetchers = {
        'deals': (DealsFetcher, registry.get('deals')),
        'contacts': (ContactsFetcher, registry.get('contacts')),
        'companies': (CompaniesFetcher, registry.get('companies'))
    }

    print("\nAvailable Fetchers:")
    for object_type, (fetcher_class, object_config) in fetchers.items():
        print(f"\n  🔄 {fetcher_class.__name__}")
        print(f"     - Object Type: {object_config.display_name}")
        print(f"     - API Endpoint: {object_config.api_endpoint}")

        # Initialize fetcher
        fetcher = fetcher_class(config, client, object_config)
        print(f"     - Checkpoint: {fetcher.checkpoint_manager.checkpoint_file}")
        print(f"     - Uses: BaseFetcher pattern (pagination, progress, checkpoint)")

    print("\n✅ All fetchers share common patterns:")
    print("   - Automatic pagination")
    print("   - Progress logging every 50 objects")
    print("   - Checkpoint/resume capability")
    print("   - Config-driven via ObjectRegistry")


def demo_report_registry():
    """Demonstrate ReportRegistry usage"""
    print_section("3. Report Registry - Config-Driven Report Definitions")

    report_registry = ReportRegistry()

    summary = report_registry.get_summary()
    print(f"\nReport Registry Summary:")
    print(f"  - Total Reports: {summary['total_reports']}")
    print(f"  - Enabled: {summary['enabled_reports']}")
    print(f"  - Disabled: {summary['disabled_reports']}")
    print(f"  - Object Types: {', '.join(summary['object_types'])}")

    print("\n\nAvailable Reports:")
    for report_id in summary['report_ids']:
        report = report_registry.get(report_id)
        status = "✅ Enabled" if report.enabled else "⏸️  Disabled"
        print(f"\n  {status} {report.name}")
        print(f"     ID: {report_id}")
        print(f"     Object Type: {report.object_type}")
        print(f"     Description: {report.description}")
        print(f"     Outputs: {', '.join(o.format for o in report.outputs)}")
        print(f"     Schedule: {report.schedule.frequency}")
        if report.note:
            print(f"     Note: {report.note}")

    print("\n✅ Reports are now JSON-configurable!")
    print("   New reports can be added by editing config/report_definitions.json")


def demo_architecture_benefits():
    """Show architecture benefits"""
    print_section("4. Architecture Benefits")

    print("\n📋 Config-Driven Architecture:")
    print("   ✓ New object types: Add to config/object_types.json")
    print("   ✓ New reports: Add to config/report_definitions.json")
    print("   ✓ No code changes needed for configuration")

    print("\n🔄 Reusable Patterns:")
    print("   ✓ BaseFetcher: Common fetch logic for all object types")
    print("   ✓ BaseAnalyzer: Common analysis pattern")
    print("   ✓ CheckpointManager: Resume-on-failure for all types")

    print("\n📊 Extensibility:")
    print("   ✓ Add ContactsFetcher: ~150 lines of code")
    print("   ✓ Add CompaniesFetcher: ~120 lines of code")
    print("   ✓ Existing fetch_deals.py still works (no breaking changes)")

    print("\n🎯 Type Safety:")
    print("   ✓ DealSnapshot, ContactSnapshot, CompanySnapshot dataclasses")
    print("   ✓ ObjectTypeConfig, ReportDefinition dataclasses")
    print("   ✓ Clear contracts between components")

    print("\n💾 Checkpoint System:")
    print("   ✓ .checkpoint_deals.json")
    print("   ✓ .checkpoint_contacts.json")
    print("   ✓ .checkpoint_companies.json")
    print("   ✓ Resume from failure for any object type")


def demo_usage_example():
    """Show practical usage example"""
    print_section("5. Practical Usage Example")

    print("\n# Example: Fetch companies with new architecture")
    print("```python")
    print("from src.config import load_config")
    print("from src.hubspot_client import HubSpotClient")
    print("from src.core import ObjectRegistry")
    print("from src.fetchers import CompaniesFetcher")
    print()
    print("# Initialize components")
    print("config = load_config()")
    print("client = HubSpotClient(config)")
    print("registry = ObjectRegistry()")
    print()
    print("# Get companies configuration")
    print("companies_config = registry.get('companies')")
    print()
    print("# Create fetcher")
    print("fetcher = CompaniesFetcher(config, client, companies_config)")
    print()
    print("# Fetch all companies (with automatic pagination & checkpoint)")
    print("companies = fetcher.fetch_all()")
    print()
    print("# Get statistics")
    print("stats = fetcher.get_summary_stats(companies)")
    print("print(f'Fetched {stats[\"total_companies\"]} companies')")
    print("```")


def main():
    """Main demonstration"""
    print()
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  PHASE 2 MULTI-OBJECT ARCHITECTURE DEMONSTRATION".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "═" * 68 + "╝")

    try:
        demo_object_registry()
        demo_fetchers()
        demo_report_registry()
        demo_architecture_benefits()
        demo_usage_example()

        print()
        print("=" * 70)
        print("  ✅ All Phase 2 components demonstrated successfully!")
        print("=" * 70)
        print()

    except Exception as e:
        print(f"\n❌ Error during demonstration: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
