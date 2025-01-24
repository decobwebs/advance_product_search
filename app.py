from flask import Flask, request, render_template
import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re

app = Flask(__name__)

# Asynchronous scraping functions
async def fetch(session, url):
    try:
        async with session.get(url) as response:
            return await response.text()
    except Exception as e:
        print(f"Error fetching URL {url}: {e}")
        return None


async def scrape_jumia(session, search_term):
    url = f'https://www.jumia.com.ng/catalog/?q={search_term}'
    html = await fetch(session, url)
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    products = []

    for item in soup.find_all('article', class_='prd'):
        name_tag = item.find('h3', class_='name')
        price_tag = item.find('div', class_='prc')
        link_tag = item.find('a', href=True)
        image_tag = item.find('img', class_='img')

        if name_tag and price_tag and link_tag:
            name = name_tag.text.strip()
            price = price_tag.text.strip()
            link = link_tag['href']
            image = image_tag['data-src'] if image_tag and 'data-src' in image_tag.attrs else None
            products.append({
                'name': name,
                'price': price,
                'url': f'https://www.jumia.com.ng{link}',
                'image': image,
                'site': 'Jumia'
            })

    return products


async def scrape_temu(session, search_term):
    url = f'https://www.temu.com/s/?q={search_term}'
    html = await fetch(session, url)
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    products = []

    for item in soup.find_all('div', class_='ProductBox__Container-sc-1y7vh44-3'):
        name_tag = item.find('a', class_='ProductCard__Title-sc-1iqz75y-2')
        price_tag = item.find('div', class_='ProductCard__Price-sc-1iqz75y-7')
        link_tag = item.find('a', href=True)
        image_tag = item.find('img')

        if name_tag and price_tag and link_tag:
            name = name_tag.text.strip()
            price = price_tag.text.strip()
            link = link_tag['href']
            image = image_tag['src'] if image_tag and 'src' in image_tag.attrs else None
            products.append({
                'name': name,
                'price': price,
                'url': f'https://www.temu.com{link}',
                'image': image,
                'site': 'Temu'
            })

    return products


async def scrape_konga(session, search_term):
    url = f'https://www.konga.com/search?search={search_term}'
    html = await fetch(session, url)
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    products = []

    for item in soup.find_all('div', class_='product-card'):
        name_tag = item.find('h3', class_='product-title')
        price_tag = item.find('span', class_='price')
        link_tag = item.find('a', href=True)

        if name_tag and price_tag and link_tag:
            name = name_tag.text.strip()
            price = price_tag.text.strip()
            link = link_tag['href']
            products.append({
                'name': name,
                'price': price,
                'url': f'https://www.konga.com{link}',
                'site': 'Konga'
            })

    return products


# Asynchronous wrapper to gather results from all scrapers
async def scrape_all_sites(search_term):
    async with aiohttp.ClientSession() as session:
        tasks = [
            scrape_jumia(session, search_term),
            scrape_temu(session, search_term),
            scrape_konga(session, search_term)
            # Add other scraping functions here if necessary
        ]
        results = await asyncio.gather(*tasks)
        return [product for site_products in results for product in site_products]


def convert_price(price_str):
    cleaned_price_str = re.sub(r'[^\d]', '', price_str)
    try:
        return int(cleaned_price_str)
    except ValueError:
        return None


@app.route('/', methods=['GET', 'POST'])
async def index():
    page = int(request.args.get('page', 1))  # Default to page 1
    items_per_page = 6  # Number of products per page

    if request.method == 'POST':
        # Retrieve form inputs
        product_name = request.form['product_name']
        price_filter = request.form.get('price_filter')
        price_value = request.form.get('price_value')
        search_type = request.form.get('search_type')

        # Perform scraping based on search type
        if search_type == 'simple':
            async with aiohttp.ClientSession() as session:
                all_products = await scrape_jumia(session, product_name)
        elif search_type == 'deep':
            async with aiohttp.ClientSession() as session:
                all_products = await scrape_all_sites(product_name)

        # Convert prices to integers and filter valid products
        for product in all_products:
            product['price_int'] = convert_price(product['price'])
        all_products = [p for p in all_products if p['price_int'] is not None]

        # Apply price filtering if specified
        if price_filter and price_value:
            price_value = int(price_value)
            if price_filter == 'above':
                filtered_products = [p for p in all_products if p['price_int'] >= price_value]
            elif price_filter == 'below':
                filtered_products = [p for p in all_products if p['price_int'] <= price_value]
        else:
            filtered_products = all_products

        # Calculate pagination
        total_products = len(filtered_products)
        total_pages = (total_products + items_per_page - 1) // items_per_page
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page

        # Paginate the products
        paginated_products = filtered_products[start_index:end_index]

        # Render the results page with products
        return render_template(
            'results.html',
            products=paginated_products,
            page=page,
            total_pages=total_pages,
            product_name=product_name,
            price_filter=price_filter,
            price_value=price_value,
            search_type=search_type
        )

    # Handle GET requests or default view
    return render_template('index.html', page=1, total_pages=1)


@app.route('/results', methods=['GET'])
async def results():
    # Get query parameters
    product_name = request.args.get('product_name', '')
    price_filter = request.args.get('price_filter')
    price_value = request.args.get('price_value')
    search_type = request.args.get('search_type', 'simple')
    page = int(request.args.get('page', 1))  # Default to page 1
    items_per_page = 6

    # Perform the search based on the search type
    if search_type == 'simple':
        async with aiohttp.ClientSession() as session:
            all_products = await scrape_jumia(session, product_name)
    elif search_type == 'deep':
        async with aiohttp.ClientSession() as session:
            all_products = await scrape_all_sites(product_name)

    # Convert prices to integers and filter valid products
    for product in all_products:
        product['price_int'] = convert_price(product['price'])
    all_products = [p for p in all_products if p['price_int'] is not None]

    # Apply price filtering if needed
    if price_filter and price_value:
        price_value = int(price_value)
        if price_filter == 'above':
            filtered_products = [p for p in all_products if p['price_int'] >= price_value]
        elif price_filter == 'below':
            filtered_products = [p for p in all_products if p['price_int'] <= price_value]
    else:
        filtered_products = all_products

    # Calculate pagination
    total_products = len(filtered_products)
    total_pages = (total_products + items_per_page - 1) // items_per_page
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page

    # Paginate products
    paginated_products = filtered_products[start_index:end_index]

    # Render the results template
    return render_template(
        'results.html',
        products=paginated_products,
        page=page,
        total_pages=total_pages,
        product_name=product_name,
        price_filter=price_filter,
        price_value=price_value,
        search_type=search_type
    )






if __name__ == '__main__':
    app.run(debug=True)
