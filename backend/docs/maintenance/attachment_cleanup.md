# Attachment Cleanup Job

**Last Updated**: November 3, 2025

## Overview

The `cleanup_attachments` management command permanently deletes soft-deleted forum attachments that have been inactive for a configurable period (default: 30 days). This automated cleanup process frees storage space while preserving recent deletions for potential restoration.

## Why This Job Exists

The forum uses a **soft delete pattern** for attachments:
- When users delete images, they're marked inactive (`is_active=False`) instead of being permanently removed
- This preserves referential integrity and allows restoration of accidentally deleted content
- However, soft-deleted files accumulate and consume storage space
- The cleanup job permanently removes old soft-deleted attachments to reclaim disk space

## Command Usage

### Basic Usage

```bash
# Run cleanup with default settings (30 days, batch size 100)
python manage.py cleanup_attachments

# Dry run (preview what would be deleted without actually deleting)
python manage.py cleanup_attachments --dry-run

# Custom retention period (45 days)
python manage.py cleanup_attachments --days=45

# Custom batch size (50 attachments per batch)
python manage.py cleanup_attachments --batch-size=50
```

### Command Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--days` | int | 30 | Delete attachments soft-deleted for this many days |
| `--dry-run` | flag | False | Show what would be deleted without actually deleting |
| `--batch-size` | int | 100 | Number of attachments to delete per batch |

### Configuration Constants

The default values are defined in `apps/forum/constants.py`:
- `ATTACHMENT_CLEANUP_DAYS = 30`
- `ATTACHMENT_CLEANUP_BATCH_SIZE = 100`

To change the defaults project-wide, modify these constants.

## Scheduling with Cron

### Recommended Schedule

Run the cleanup job weekly during low-traffic periods:

```bash
# Add to crontab (crontab -e)
# Runs every Sunday at 2 AM
0 2 * * 0 /path/to/venv/bin/python /path/to/manage.py cleanup_attachments

# With email notifications on errors
0 2 * * 0 /path/to/venv/bin/python /path/to/manage.py cleanup_attachments || mail -s "Attachment cleanup failed" admin@example.com
```

### Alternative Schedules

```bash
# Daily at 3 AM (for high-volume sites)
0 3 * * * /path/to/venv/bin/python /path/to/manage.py cleanup_attachments

# Monthly on the 1st at 4 AM (for low-volume sites)
0 4 1 * * /path/to/venv/bin/python /path/to/manage.py cleanup_attachments
```

### Using systemd Timer (Linux)

Create `/etc/systemd/system/cleanup-attachments.service`:
```ini
[Unit]
Description=Cleanup soft-deleted forum attachments
After=network.target

[Service]
Type=oneshot
User=www-data
WorkingDirectory=/path/to/project
Environment="DJANGO_SETTINGS_MODULE=plant_community_backend.settings"
ExecStart=/path/to/venv/bin/python manage.py cleanup_attachments
```

Create `/etc/systemd/system/cleanup-attachments.timer`:
```ini
[Unit]
Description=Run attachment cleanup weekly
Requires=cleanup-attachments.service

[Timer]
OnCalendar=Sun *-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
sudo systemctl enable cleanup-attachments.timer
sudo systemctl start cleanup-attachments.timer
sudo systemctl status cleanup-attachments.timer
```

## How It Works

### Query Logic

The command queries for attachments matching:
```python
Attachment.objects.filter(
    is_active=False,
    deleted_at__lte=cutoff_date
)
```

Where `cutoff_date = timezone.now() - timedelta(days=ATTACHMENT_CLEANUP_DAYS)`

### Performance Optimization

A **partial index** on `(is_active, deleted_at)` WHERE `is_active=False` significantly speeds up the query by only indexing soft-deleted records.

Migration: `0004_add_attachment_cleanup_index.py`

### Batch Processing

- Processes attachments in batches (default: 100 per batch)
- Each deletion is wrapped in a transaction for atomicity
- If a batch fails, the error is logged and the command continues
- This prevents memory issues on large datasets

### File Deletion

For each attachment:
1. Delete the physical image file from storage (S3 or local)
2. Delete the database record using `hard_delete()`
3. Log the deletion for audit purposes

## Monitoring and Logging

### Log Messages

The command produces structured logs with `[CLEANUP]` prefix:

```python
logger.info(f'[CLEANUP] Hard-deleted attachment: {filename}')
logger.error(f'[CLEANUP] Failed to delete attachment {id}: {error}')
```

### Monitoring Checklist

1. **Check for failed deletions**: `grep "CLEANUP.*Failed" /path/to/logs/django.log`
2. **Monitor disk space**: Ensure storage usage decreases after cleanup runs
3. **Review deletion counts**: Verify the summary report matches expectations
4. **Check execution time**: Long runtimes may indicate performance issues

### Example Output

```
Permanently deleting 247 attachments in batches of 100...
  Deleted 10/247...
  Deleted 20/247...
  ...
  Deleted 247/247...

✅ Cleanup complete:
  - Successfully deleted: 245 attachments
  - Failed: 2 attachments
  - Cutoff date: 2025-10-04 02:00:00
```

## Restoring Accidentally Deleted Attachments

If an attachment was soft-deleted but not yet cleaned up, administrators can restore it:

```python
from apps.forum.models import Attachment

# Find the soft-deleted attachment
attachment = Attachment.objects.get(id='uuid-here')

# Restore it (sets is_active=True, clears deleted_at)
attachment.restore()
```

**Note**: Once the cleanup job runs, restoration is **not possible** as the physical file is permanently deleted.

## Troubleshooting

### Issue: Cleanup job runs too slowly

**Symptoms**: Command takes hours to complete, high CPU/memory usage

**Solutions**:
1. Reduce batch size: `--batch-size=50`
2. Check if partial index exists (migration 0004)
3. Run during off-peak hours only
4. Consider archiving to cold storage instead of deleting

### Issue: Files not deleted from S3

**Symptoms**: Database records removed but S3 storage usage unchanged

**Solutions**:
1. Verify AWS credentials are configured correctly
2. Check S3 bucket permissions allow deletion
3. Review CloudWatch logs for S3 API errors
4. Run with `--dry-run` to verify file paths

### Issue: Too many files deleted

**Symptoms**: Cleanup deleted more files than expected

**Prevention**:
1. Always run `--dry-run` first to preview
2. Use longer retention period: `--days=60`
3. Review soft-delete timestamps before cleanup
4. Implement backups before running cleanup

### Issue: Transaction deadlocks

**Symptoms**: `DeadlockDetected` errors during cleanup

**Solutions**:
1. Reduce batch size: `--batch-size=25`
2. Run when forum activity is low (2-4 AM)
3. Check for long-running transactions blocking cleanup

## Testing

The cleanup command has comprehensive test coverage:

```bash
# Run cleanup tests
python manage.py test apps.forum.tests.test_attachment_soft_delete --keepdb -v 2

# Specific tests
python manage.py test apps.forum.tests.test_attachment_soft_delete.AttachmentSoftDeleteTests.test_cleanup_command_deletes_old_attachments
python manage.py test apps.forum.tests.test_attachment_soft_delete.AttachmentSoftDeleteTests.test_cleanup_command_dry_run_doesnt_delete
```

Test coverage includes:
- 30-day threshold enforcement
- Dry-run safety (no deletions)
- Batch processing behavior
- Error handling and logging

## Related Documentation

- [Soft Delete Pattern](../architecture/soft_delete_pattern.md)
- [Forum Models](../forum/models.md)
- [Storage Configuration](../deployment/storage.md)
- [Cron Job Setup](../deployment/scheduled_jobs.md)

## Appendix: Manual Cleanup

If the automated job fails, you can manually clean up old attachments:

```python
from datetime import timedelta
from django.utils import timezone
from apps.forum.models import Attachment
from apps.forum.constants import ATTACHMENT_CLEANUP_DAYS

# Find old soft-deleted attachments
cutoff = timezone.now() - timedelta(days=ATTACHMENT_CLEANUP_DAYS)
old_attachments = Attachment.objects.filter(
    is_active=False,
    deleted_at__lte=cutoff
)

print(f"Found {old_attachments.count()} attachments to delete")

# Delete one at a time with error handling
for attachment in old_attachments:
    try:
        filename = attachment.original_filename
        attachment.hard_delete()
        print(f"Deleted: {filename}")
    except Exception as e:
        print(f"Failed to delete {attachment.id}: {e}")
```

**Warning**: Manual cleanup should only be used in emergencies. Always prefer the management command.
