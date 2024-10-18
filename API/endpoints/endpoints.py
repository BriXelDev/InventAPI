from flask import Blueprint, make_response, request, jsonify
from API import db
from ..database.db import Product
from API.cache import cache
from ..cache.cache import redis_client, clear_product_quantity_cache
import json, re

product_blueprint = Blueprint('products', __name__)
 
 # Regex para permitir solo letras, números y espacios
regex = r'^[a-zA-Z0-9\s]+$'

@product_blueprint.route('/products/post', methods=['POST'])
def create_product():
    """
    Create a new product
    ---
    tags:
      - Products
    summary: Builds a new product
    description: Creates a new product based on the parameters offered. Then creates a SKU for the product automatically. Returns the new product or an error.
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - Product
            - Description
            - Quantity
            - Brand
            - Price
          properties:
            Product:
              type: string
              description: "Name of the product"
            Description:
              type: string
              description: "Description of the product"
            Quantity:
              type: integer
              description: "Quantity available"
            Brand:
              type: string
              description: "Brand of the product"
            Department:
              type: string
              description: "Department which the product belongs to"
            Price:
              type: number
              format: float
              description: "Price of the product per unit"
    responses:
      201:
        description: Product created successfully
      500:
        description: Error creating product
    """
    try:
        data = request.get_json()

        # Validaciones
        if not data:
            return make_response(json.dumps({"Message": "Request body cannot be empty"}, indent=1), 400, {'Content-Type': 'application/json'})
        required_fields = ['Product', 'Description', 'Quantity', 'Brand', 'Department', 'Price']
        for field in required_fields:
            if field not in data:
                return make_response(json.dumps({"Message": f"Missing field: {field}"}, indent=4), 400, {'Content-Type': 'application/json'})
                
        if not isinstance(data['Product'], str) or not re.match(regex, data['Product']):
            return make_response(json.dumps({"Message": "Product name can only contain letters, numbers, and spaces"}, indent=4), 400, {'Content-Type': 'application/json'})
        if not isinstance(data['Description'], str):
            return make_response(json.dumps({"Message": "Description must be a string"}, indent=4), 400, {'Content-Type': 'application/json'})
        if not isinstance(data['Quantity'], int) or data['Quantity'] < 0:
            return make_response(json.dumps({'Message': "Quantity must be a non-negative integer"}, indent=4), 400, {'Content-Type': 'application/json'})
        if not isinstance(data['Brand'], str) or not re.match(regex, data['Brand']):
            return make_response(json.dumps({"Message": "Brand can only contain letters, numbers, and spaces"}, indent=4), 400, {'Content-Type': 'application/json'})
        if not isinstance(data['Department'], str) or not re.match(regex, data['Department']):
            return make_response(json.dumps({"Message": "Department can only contain letters, numbers, and spaces"}, indent=4), 400, {'Content-Type': 'application/json'})
        if not isinstance(data['Price'], (int, float)) or data['Price'] < 0:
            return make_response(json.dumps({"Message": 'Price must be a non-negative number'}, indent=4), 400, {'Content-Type': 'application/json'})

        # Crear el nuevo producto y su SKU
        new_product = Product(Product=data['Product'], Description=data['Description'], Quantity=data['Quantity'], Brand=data['Brand'], Department=data['Department'], Price=data['Price'])
        db.session.add(new_product)
        db.session.commit()
        redis_client.delete("all_products")
        clear_product_quantity_cache()

        product_json = {
            'SKU': new_product.SKU,
            'Product': new_product.Product,
            'Description': new_product.Description,
            'Brand': new_product.Brand,
            'Department': new_product.Department,
            'Quantity': new_product.Quantity,
            'Price': new_product.Price
        }
        return make_response(json.dumps({'message': 'Product created successfully', 'Product': product_json}, indent=4), 201, {'Content-Type': 'application/json'})
    except Exception as e:
        return make_response(json.dumps({'message': f'Product not created: {str(e)}'}, indent=4), 500, {'Content-Type': 'application/json'})

@product_blueprint.route('/products/getall', methods=['GET'])
def get_all_products():
    """
    Retrieve all products
    ---
    tags:
      - Products
    summary: Get all products
    description: Retrieve all products from the inventory. Returns all products or an error if there is an issue.
    responses:
      200:
        description: List of all products
        content:
          application/json:
            example:
              Products:
                - SKU: ABC123456
                  Product: "Product A"
                  Description: "Description of Product A"
                  Quantity: 100
                  Brand: "Manufacturer C"
                  Department: "Section W"
                  Price: 10.00
                - SKU: DEF789012 
                  Product: "Product B"
                  Description: "Description of Product B"
                  Quantity: 50
                  Brand: "Manufacturer D"
                  Department: "Section Z"
                  Price: 20.00
      500:
        description: Product not found or server error
        content:
          application/json:
            example:
              Message: "Product not found"
              Error: "Description of the error"
    """
    try:
        cached_products = redis_client.get('all_products')
        if cached_products:
            products_data = json.loads(cached_products)
            return make_response(json.dumps(products_data), 200, {'Content-Type': 'application/json'})
        
        products = Product.query.order_by(Product.SKU.asc()).all()
        products_json = [ 
            {
                'SKU': product.SKU,
                'Product': product.Product,
                'Description': product.Description,
                'Brand': product.Brand,
                'Department' : product.Department,
                'Quantity': product.Quantity,
                'Price': product.Price
            }
            for product in products
        ]
        response = {'Products': products_json}
        redis_client.setex('all_products', 3600, json.dumps(response))
        return make_response(json.dumps(response), 200, {'Content-Type': 'application/json'})
    except Exception as e:
        return make_response(json.dumps({'message': f'Product not created: {str(e)}'}, indent=4), 500, {'Content-Type': 'application/json'})

@product_blueprint.route('/products/getbyquantity/', methods=['GET'])
def get_products_byQuantity():
    """
    Get coincident products by quantity
    ---
    tags:
      - Products
    summary: Fetches products sorted by quantity
    description: Returns products that have equal or greater quantity than the specified. Returns an error if there are any issues. Enables pagination for a better sorting of the products.
    parameters:
      - name: quantity
        in: query
        type: integer
        required: true
        description: "Target quantity to match"
      - name: page
        in: query
        type: integer
        required: false
        description: "Page number for pagination"
      - name: per_page
        in: query
        type: integer
        required: false
        description: "Number of items per page"
    responses:
      200:
        description: List of products
      500:
        description: Error retrieving products
    """
    try:
        quantity = request.args.get('quantity', default=0, type=int)
        page = request.args.get('page', default=1, type=int)
        per_page = request.args.get('per_page', default=10, type=int)

        #Validaciones
        if quantity < 0:
            return make_response(json.dumps({'Error': 'The provided quantity must be greater than zero'}), 400, {'Content-Type': 'application/json'})
        
        if page <= 0 or per_page <= 0:
            return make_response(json.dumps({'Error': 'Page and per_page must be greater than zero'}), 400, {'Content-Type': 'application/json'})

        # Comprobar el caché de Redis
        cache_key = f'products_quantity_{quantity}_{page}_{per_page}'
        cached_products = redis_client.get(cache_key)

        if cached_products:
            products_data = json.loads(cached_products)
            return make_response(json.dumps(products_data), 200, {'Content-Type': 'application/json'})

        products = Product.query.filter(Product.Quantity >= quantity).order_by(Product.SKU.asc()).all()
        start_index = (page -1) * per_page
        end_index = start_index + per_page
        paginated_products = products[start_index:end_index]

        products_json = [
            {
                'SKU': product.SKU,
                'Product': product.Product,
                'Description': product.Description,
                'Brand': product.Brand,
                'Department': product.Department,
                'Quantity': product.Quantity,
                'Price': product.Price
            }
            for product in paginated_products
        ]
        
        # Almacenar en caché
        response = {'Products': products_json}
        redis_client.setex(cache_key, 3600, json.dumps(response))

        return make_response(json.dumps(response), 200, {'Content-Type': 'application/json'})
    except Exception as e:
        return make_response(json.dumps({'message': f'Product not retrieved: {str(e)}'}, indent=4), 500, {'Content-Type': 'application/json'})

@product_blueprint.route('/products/getby/<string:SKU>', methods=['GET'])
def get_product(SKU):
    """
    Get product by SKU
    ---
    tags:
      - Products
    summary: Gets products by their SKU
    description: Sends back a product that matches the SKU provided. Or an error if there is any.
    parameters:
      - name: SKU
        in: path
        type: string
        required: true
        description: "SKU of the product to search"
    responses:
      200:
        description: Product found
      404:
        description: Product not found
      500:
        description: Error retrieving product
    """
    try:
        # Comprobar el caché de Redis
        cache_key = f'product_{SKU}'
        cached_product = redis_client.get(cache_key)

        if cached_product:
            product_data = json.loads(cached_product)
            return make_response(json.dumps(product_data), 200, {'Content-Type': 'application/json'})

        product = Product.query.filter_by(SKU=SKU).first()
        if product:
            product_json = {
                'SKU': product.SKU,
                'Product': product.Product,
                'Description': product.Description,
                'Brand': product.Brand,
                'Department': product.Department,
                'Quantity': product.Quantity,
                'Price': product.Price
            }
            # Almacenar en caché
            redis_client.setex(cache_key, 3600, json.dumps({'Product': product_json}))
            return make_response(json.dumps({'Product': product_json}), 200, {'Content-Type': 'application/json'})
        
        return make_response(json.dumps({'Message': 'Product not found'}, indent=4), 404, {'Content-Type': 'application/json'})
    except Exception as e:
        return make_response(json.dumps({'message': f'Product not created: {str(e)}'}, indent=4), 500, {'Content-Type': 'application/json'})
    
@product_blueprint.route('/products/put/<string:SKU>', methods=['PUT'])
def update_product(SKU):
    """
    Update product by their SKU
    ---
    tags:
      - Products
    summary: Changes product parameters
    description: Allows to change all the paramters of a product that matches the SKU. Returns the updated product or an error if that is the case.
    parameters:
      - name: SKU
        in: path
        type: string
        required: true
        description: "SKU of the product to be updated"
      - name: body
        in: body
        required: true
        schema:
          type: object
          required:
            - Product
            - Description
            - Quantity
            - Brand
            - Department
            - Price
          properties:
            Product:
              type: string
              description: "Name of the product"
            Description:
              type: string
              description: "Description of the product"
            Quantity:
              type: integer
              description: "Quantity available"
            Brand:
              type: string
              description: "Brand of the product"
            Department:
              type: string
              description: "Department which the product belongs to"
            Price:
              type: number
              format: float
              description: "Price of the product per unit"
    responses:
      200:
        description: Product updated successfully
      404:
        description: Product not found
      500:
        description: Error updating product
    """
    
    try:
      #Validaciones
        product = Product.query.filter_by(SKU=SKU).first()
        if not product:
          return make_response(json.dumps({'Message': 'Product not found'}, indent=4), 404, {'Content-Type': 'application/json'})
      
        data = request.get_json()
        if not data:
          return make_response(json.dumps({'Message': 'Invalid input', 'Error': 'Request body is missing'}, indent=4), 400, {'Content-Type': 'application/json'})
        
        required_fields = ['Product', 'Description', 'Quantity', 'Brand', 'Department', 'Price']
        for field in required_fields:
          if field not in data:
            return make_response(json.dumps({'Message': 'Invalid input', 'Error': f'Missing field: {field}'}, indent=4), 400, {'Content-Type': 'application/json'})

        if not isinstance(data['Product'], str) or not re.match(regex, data['Product']):
            return make_response(json.dumps({'Message': 'Invalid input', 'Error': "Product name can only contain letters, numbers, and spaces"}, indent=4), 400, {'Content-Type': 'application/json'})
        
        if not isinstance(data['Quantity'], int) or data['Quantity'] < 0:
            return make_response(json.dumps({'Message': 'Invalid input', 'Error': 'Quantity must be a non-negative integer'}, indent=4), 400, {'Content-Type': 'application/json'})
        
        if not isinstance(data['Price'], (int, float)) or data['Price'] < 0:
            return make_response(json.dumps({'Message': 'Invalid input', 'Error': 'Price must be a non-negative number'}, indent=4), 400, {'Content-Type': 'application/json'})
        
        if not isinstance(data['Brand'], str) or not re.match(regex, data['Brand']):
            return make_response(json.dumps({'Message': 'Invalid input', 'Error': "Brand can only contain letters, numbers, and spaces"}, indent=4), 400, {'Content-Type': 'application/json'})
        
        if not isinstance(data['Department'], str) or not re.match(regex, data['Department']):
            return make_response(json.dumps({'Message': 'Invalid input', 'Error': "Department can only contain letters, numbers, and spaces"}, indent=4), 400, {'Content-Type': 'application/json'})
        
        
        product.Product = data['Product']
        product.Description = data['Description']
        product.Quantity = data['Quantity']
        product.Brand = data['Brand']
        product.Department = data['Department']
        product.Price = data['Price']
        db.session.commit()
            
        redis_client.delete(f"product_{SKU}")
        redis_client.delete("all_products")
        clear_product_quantity_cache()

        product_json = {
          'SKU': product.SKU,
          'Product': product.Product,
          'Description': product.Description,
          'Brand': product.Brand,
          'Department': product.Department,
          'Quantity': product.Quantity,
          'Price': product.Price
        }
        return make_response(json.dumps({'Message': 'Product updated', 'Product': product_json}, indent=4), 200, {'Content-Type': 'application/json'})
    except Exception as e:
        return make_response(json.dumps({'message': f'Product not created: {str(e)}'}, indent=4), 500, {'Content-Type': 'application/json'})

@product_blueprint.route('/products/delete/<string:SKU>', methods=['DELETE'])
def delete_product(SKU):
    """
    Delete product by their SKU
    ---
    tags:
      - Products
    summary: Deletes products
    description: Erase a product according to the SKU. Returns a message indicating that it has been deleted.
    parameters:
      - name: SKU
        in: path
        type: string
        required: true
        description: "SKU of the product"
    responses:
      200:
        description: Product deleted successfully
      404:
        description: Product not found
      500:
        description: Error deleting product
    """

    try:
        product = Product.query.filter_by(SKU=SKU).first()
        if product:
            db.session.delete(product)
            db.session.commit()
            
            redis_client.delete(f"product_{SKU}")
            redis_client.delete("all_products")
            clear_product_quantity_cache()

            return make_response(jsonify({'Message': 'Product deleted'}), 200)
        return make_response(jsonify({'Message': 'Product not deleted'}), 404)
    except Exception as e:
        return make_response(json.dumps({'message': f'Product not created: {str(e)}'}, indent=4), 500, {'Content-Type': 'application/json'})
    
@product_blueprint.route('/products/patch/<string:SKU>', methods=['PATCH'])
def patch_product(SKU):
    """
    Partially update product by SKU
    ---
    tags:
      - Products
    summary: Update products
    description: Permits updating one or more parameters of a product that equals the provided SKU. To use, delete the parameters that won't be changed, then update the remaining ones. Returns the updated product or an error accordingly.
    parameters:
      - name: SKU
        in: path
        type: string
        required: true
        description: "SKU of the product that needs to be changed"
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            Product:
              type: string
              description: "Name of the product"
            Description:
              type: string
              description: "Description of the product"
            Quantity:
              type: integer
              description: "Quantity available"
            Brand:
              type: string
              description: "Brand of the product"
            Department:
              type: string
              description: "Department which the product belongs to"
            Price:
              type: number
              format: float
              description: "Price of the product per unit"
    responses:
      200:
        description: Product patched successfully
      404:
        description: Product not found
      500:
        description: Error patching product
    """
    
    try:
        product = Product.query.filter_by(SKU=SKU).first()
        if not product:
            return make_response(json.dumps({'Message': 'Product not found'}, indent=4), 404, {'Content-Type': 'application/json'})
        
        data = request.get_json()
        if not data:
            return make_response(json.dumps({'Message': 'Invalid input', 'Error': 'Request body is missing'}, indent=4), 400, {'Content-Type': 'application/json'})
        
        if 'Product' in data:
            if not isinstance(data['Product'], str) or not re.match(regex, data['Product']):
                return make_response(json.dumps({'Message': 'Invalid input', 'Error': 'Product name can only contain letters, numbers, and spaces'}, indent=4), 400, {'Content-Type': 'application/json'})
            product.Name = data['Name']

        if 'Description' in data:
            if not isinstance(data['Description'], str):
                return make_response(json.dumps({'Message': 'Invalid input', 'Error': 'Description must be a string'}, indent=4), 400, {'Content-Type': 'application/json'})
            product.Description = data['Description']

        if 'Quantity' in data:
            if not isinstance(data['Quantity'], int) or data['Quantity'] < 0:
                return make_response(json.dumps({'Message': 'Invalid input', 'Error': 'Quantity must be a non-negative integer'}, indent=4), 400, {'Content-Type': 'application/json'})
            product.Quantity = data['Quantity']

        if 'Price' in data:
            if not isinstance(data['Price'], (int, float)) or data['Price'] < 0:
                return make_response(json.dumps({'Message': 'Invalid input', 'Error': 'Price must be a non-negative number'}, indent=4), 400, {'Content-Type': 'application/json'})
            product.Price = data['Price']
        
        if 'Brand' in data:
            if not isinstance(data['Brand'], str) or not re.match(regex, data['Brand']):
                return make_response(json.dumps({'Message': 'Invalid input', 'Error': "Brand can only contain letters, numbers, and spaces"}, indent=4), 400, {'Content-Type': 'application/json'})
            product.Price = data['Brand']

        if 'Department' in data:
            if not isinstance(data['Department'], str) or not re.match(regex, data['Department']):
                return make_response(json.dumps({'Message': 'Invalid input', 'Error': "Department can only contain letters, numbers, and spaces"}, indent=4), 400, {'Content-Type': 'application/json'})
            product.Price = data['Brand']
        
        db.session.commit() 

        redis_client.delete(f"product_{SKU}")
        redis_client.delete("all_products")
        clear_product_quantity_cache()

        product_json = {
            'SKU': product.SKU,
            'Product': product.Product,
            'Description': product.Description,
            'Brand': product.Brand,
            'Department': product.Department,
            'Quantity': product.Quantity,
            'Price': product.Price
        }
        return make_response(json.dumps({'Message': 'Product patched successfully', 'Product': product_json}, indent=4), 200, {'Content-Type': 'application/json'})
    except Exception as e:
        return make_response(json.dumps({'message': f'Product not created: {str(e)}'}, indent=4), 500, {'Content-Type': 'application/json'})

