import os
from PIL import Image
import cairosvg
import io

# Create static directory if it doesn't exist
if not os.path.exists('static'):
    os.makedirs('static')

# Convert SVG to PNG first
png_data = cairosvg.svg2png(url='static/icon.svg', output_width=256, output_height=256)
png_image = Image.open(io.BytesIO(png_data))

# Create ICO file with multiple sizes
sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
ico_images = []

for size in sizes:
    resized_image = png_image.resize(size, Image.LANCZOS)
    ico_images.append(resized_image)

# Save as ICO
ico_images[0].save('static/favicon.ico', format='ICO', sizes=[(img.width, img.height) for img in ico_images])

print("Icon converted successfully to static/favicon.ico")