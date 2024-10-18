from API import db
import random, string

class Product(db.Model):
    __tablename__ = 'products'

    SKU = db.Column(db.String(9), primary_key=True, unique=True, nullable=False)
    Product = db.Column(db.String(80), nullable=False)
    Description = db.Column(db.String(1500), nullable=False)
    Brand = db.Column(db.String(80), nullable=False)
    Department = db.Column(db.String(90), nullable=False)
    Quantity = db.Column(db.Integer, nullable=False)
    Price = db.Column(db.Float, nullable=False)

    def __init__(self, Product, Description, Quantity, Brand, Department, Price):
        self.SKU = generate_sku(Department, Product, Brand)
        self.Product = Product
        self.Description = Description
        self.Brand = Brand
        self.Department = Department
        self.Quantity = Quantity
        self.Price = Price

def generate_sku(department, product, brand):
    first_letter = department[0].upper()
    second_letter = product[0].upper()
    third_letter = brand[0].upper()

    while True:
        random_digits = ''.join(random.choices(string.digits, k=6))

        sku = f"{first_letter}{second_letter}{third_letter}{random_digits}"

        if not Product.query.filter_by(SKU=sku).first():
            break

    return sku

db.create_all()
