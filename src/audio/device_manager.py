import sounddevice as sd


def list_input_devices() -> list:
    """Returns list of {id, name, channels, sample_rate} for all input devices."""
    devices = []
    for i, d in enumerate(sd.query_devices()):
        if d['max_input_channels'] > 0:
            devices.append({
                'id': i,
                'name': d['name'],
                'channels': d['max_input_channels'],
                'sample_rate': int(d['default_samplerate']),
            })
    return devices


def get_default_device() -> dict:
    idx = sd.default.device[0]
    d = sd.query_devices(idx)
    return {
        'id': idx,
        'name': d['name'],
        'channels': d['max_input_channels'],
        'sample_rate': int(d['default_samplerate']),
    }


def validate_device(device_id: int) -> bool:
    try:
        sd.check_input_settings(device=device_id, channels=1, samplerate=16000)
        return True
    except Exception:
        return False
