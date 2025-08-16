from flask import Blueprint, request, jsonify
from flask_login import login_required
from sqlalchemy import func
from extensions import db
from models import Product, StockMovement, Sale, SaleItem, Purchase, PurchaseItem
from forecasting import forecast_demand

api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.get("/products")
@login_required
def list_products():
    products = Product.query.order_by(Product.name).all()
    return jsonify([{
        "id": p.id,
        "sku": p.sku,
        "name": p.name,
        "unit": p.unit,              # ← add this
        "barcode": p.barcode,
        "reorder_point": p.reorder_point,
        "unit_price": p.unit_price
    } for p in products])



@api_bp.post("/products")
@login_required
def create_product():
    data = request.json or {}
    unit_price = float(data.get("unit_price") or 0)
    opening_stock = int(data.get("opening_stock") or 0)

    p = Product(
        sku=data["sku"],
        name=data["name"],
        category=data.get("category"),
        unit=data.get("unit", "unit"),
        barcode=data.get("barcode"),
        reorder_point=data.get("reorder_point", 0),
        unit_price=unit_price
    )
    db.session.add(p); db.session.flush()

    # If opening stock > 0, create an IN stock movement
    if opening_stock > 0:
        mv = StockMovement(product_id=p.id, qty=opening_stock, type="IN", source="opening")
        db.session.add(mv)

    db.session.commit()
    return jsonify({"id": p.id}), 201


@api_bp.get("/stock")
@login_required
def stock_balances():
    rows = (db.session.query(StockMovement.product_id, func.sum(StockMovement.qty))
            .group_by(StockMovement.product_id).all())
    balances = {pid: int(total or 0) for pid, total in rows}
    # attach product names
    products = Product.query.all()
    out = []
    for p in products:
        out.append({
            "product_id": p.id,
            "name": p.name,
            "sku": p.sku,
            "stock": balances.get(p.id, 0),
            "reorder_point": p.reorder_point
        })
    return jsonify(out)

@api_bp.post("/sales")
@login_required
def create_sale():
    data = request.json
    items = data["items"]  # [{product_id, qty, unit_price}]
    sale = Sale(total_amount=sum(i["qty"]*i["unit_price"] for i in items))
    db.session.add(sale); db.session.flush()
    for it in items:
        si = SaleItem(sale_id=sale.id, product_id=it["product_id"],
                      qty=it["qty"], unit_price=it["unit_price"])
        db.session.add(si)
        mv = StockMovement(product_id=it["product_id"], qty=-abs(it["qty"]),
                           type="OUT", source="sale")
        db.session.add(mv)
    db.session.commit()
    return jsonify({"sale_id": sale.id})

@api_bp.post("/purchases")
@login_required
def create_purchase():
    data = request.json
    items = data["items"]  # [{product_id, qty, unit_cost}]
    purchase = Purchase(total_cost=sum(i["qty"]*i["unit_cost"] for i in items))
    db.session.add(purchase); db.session.flush()
    for it in items:
        pi = PurchaseItem(purchase_id=purchase.id, product_id=it["product_id"],
                          qty=it["qty"], unit_cost=it["unit_cost"])
        db.session.add(pi)
        mv = StockMovement(product_id=it["product_id"], qty=abs(it["qty"]),
                           type="IN", source="purchase", unit_cost=it["unit_cost"])
        db.session.add(mv)
    db.session.commit()
    return jsonify({"purchase_id": purchase.id})

@api_bp.get("/forecast/<int:product_id>")
@login_required
def product_forecast(product_id):
    return jsonify(forecast_demand(product_id))

@api_bp.post("/sync")
@login_required
def sync_batch():
    """
    Accepts {sales: [...], purchases: [...], products: [...]} created offline.
    Idempotency key is recommended in production; omitted here for brevity.
    """
    payload = request.json or {}
    created = {"sales": 0, "purchases": 0, "products": 0}

    for p in payload.get("products", []):
        if not Product.query.filter_by(sku=p["sku"]).first():
            db.session.add(Product(sku=p["sku"], name=p["name"],
                                   barcode=p.get("barcode"), reorder_point=p.get("reorder_point",0)))
            created["products"] += 1

    for s in payload.get("sales", []):
        items = s["items"]
        sale = Sale(total_amount=sum(i["qty"]*i["unit_price"] for i in items))
        db.session.add(sale); db.session.flush()
        for it in items:
            db.session.add(SaleItem(sale_id=sale.id, product_id=it["product_id"],
                                    qty=it["qty"], unit_price=it["unit_price"]))
            db.session.add(StockMovement(product_id=it["product_id"], qty=-abs(it["qty"]),
                                         type="OUT", source="sale"))
        created["sales"] += 1

    for p in payload.get("purchases", []):
        items = p["items"]
        purchase = Purchase(total_cost=sum(i["qty"]*i["unit_cost"] for i in items))
        db.session.add(purchase); db.session.flush()
        for it in items:
            db.session.add(PurchaseItem(purchase_id=purchase.id, product_id=it["product_id"],
                                        qty=it["qty"], unit_cost=it["unit_cost"]))
            db.session.add(StockMovement(product_id=it["product_id"], qty=abs(it["qty"]),
                                         type="IN", source="purchase", unit_cost=it["unit_cost"]))
        created["purchases"] += 1

    db.session.commit()
    return jsonify({"created": created})

@api_bp.get("/activity")
@login_required
def recent_activity():
    limit = int(request.args.get("limit", 10))
    # Join movements with product for name/sku
    q = (db.session.query(StockMovement, Product)
         .join(Product, StockMovement.product_id == Product.id)
         .order_by(StockMovement.timestamp.desc())
         .limit(limit)
         .all())
    out = []
    for mv, p in q:
        out.append({
            "timestamp": mv.timestamp.isoformat(),
            "sku": p.sku,
            "name": p.name,
            "type": mv.type,
            "qty": mv.qty
        })
    return jsonify(out)
