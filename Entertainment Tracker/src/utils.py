def format_time(hours):
    total_seconds = round(hours * 3600)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}:{minutes:02d}:{seconds:02d}"


def parse_time(time_text):
    parts = time_text.split(":")
    if len(parts) != 3:
        raise ValueError
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2])
    if hours < 0 or not 0 <= minutes <= 59 or not 0 <= seconds <= 59:
        raise ValueError
    return hours + minutes / 60 + seconds / 3600
