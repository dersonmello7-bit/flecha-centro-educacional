class PrivateResponseMiddleware:
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        response=self.get_response(request)
        response['Cache-Control']='no-store, private'
        response['Referrer-Policy']='same-origin'
        response['X-Robots-Tag']='noindex, nofollow'
        response['Permissions-Policy']='camera=(), microphone=(), geolocation=()'
        if not request.path.startswith('/administracao/'):
            response['Content-Security-Policy']="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response
