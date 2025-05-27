import openai

def generate_image(prompt):
    response = openai.Image.create(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        n=1
    )
    return response['data'][0]['url']
