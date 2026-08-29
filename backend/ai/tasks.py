from celery import shared_task

from files.models import DriveFile

from . import service


@shared_task
def generate_summary_task(drive_file_id):
    try:
        drive_file = DriveFile.objects.select_related("user").get(id=drive_file_id)
    except DriveFile.DoesNotExist:
        return
    try:
        service.summarize_file(drive_file)
    except Exception:
        # Best-effort: a failed summary just means GET .../summary keeps
        # returning 404 rather than ever completing. Nothing else depends
        # on this succeeding.
        pass


@shared_task
def categorize_files_task(file_ids, billable=True):
    files = list(DriveFile.objects.select_related("user").filter(id__in=file_ids))
    try:
        service.categorize_files(files, billable=billable)
    except Exception:
        pass
