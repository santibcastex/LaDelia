from main import app

# Vercel serverless function
def handler(request):
    return app(request)