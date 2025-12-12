import tempfile
import os
import sys
from pathlib import Path

# Add parent directory to path so we can import app module
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import IngestionConfig, SourceConfig
from copilot_events import create_publisher
from app.service import IngestionService


def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = os.path.join(tmpdir, 'archives')
        os.makedirs(storage_path)

        source_dir = os.path.join(tmpdir, 'sources')
        os.makedirs(source_dir)
        test_file = os.path.join(source_dir, 'test.mbox')
        with open(test_file, 'w') as f:
            f.write('From: test@example.com\nSubject: Test\n\nContent')

        config = IngestionConfig(storage_path=storage_path)
        source = SourceConfig(
            name='test-source',
            source_type='local',
            url=test_file,
        )
        config.sources = [source]

        publisher = create_publisher(message_bus_type='noop')
        publisher.connect()
        service = IngestionService(config, publisher)

        success = service.ingest_archive(source, max_retries=1)

        if success:
            print('\u2713 Local ingestion test passed')
        else:
            print('\u2717 Local ingestion test failed')
            raise SystemExit(1)


if __name__ == "__main__":
    main()
