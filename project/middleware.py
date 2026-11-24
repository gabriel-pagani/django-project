class PermissionsPolicyMiddleware:
    """Desliga os recursos do navegador que o sistema não usa.

    Uma view que precisar de um deles (a câmera, por exemplo) põe o próprio
    cabeçalho na resposta, e este não o sobrescreve.
    """

    FEATURES = {
        'accelerometer': '()',
        'autoplay': '()',
        'camera': '()',
        'display-capture': '()',
        'encrypted-media': '()',
        'fullscreen': '(self)',
        'geolocation': '()',
        'gyroscope': '()',
        'magnetometer': '()',
        'microphone': '()',
        'midi': '()',
        'payment': '()',
        'usb': '()',
        'xr-spatial-tracking': '()',
    }

    POLICY = ', '.join(f'{feature}={origins}' for feature, origins in FEATURES.items())

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('Permissions-Policy', self.POLICY)
        return response
