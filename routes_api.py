from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import func
from extensions import db
from models import Product, StockMovement, Sale, SaleItem, Purchase, PurchaseItem
from forecasting import forecast_demand
from sqlalchemy.orm import joinedload

api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.get("/stock")
@login_required
def stock_balances():
    # sum movements but only for products in this business
    rows = (db.session.query(StockMovement.product_id, func.sum(StockMovement.qty))
            .join(Product, Product.id == StockMovement.product_id)
            .filter(Product.business_id == current_user.business_id)
            .group_by(StockMovement.product_id).all())
    totals = {pid: int(total or 0) for pid, total in rows}
    products = Product.query.filter_by(business_id=current_user.business_id).all()
    return jsonify([{
        "product_id": p.id, "name": p.name, "sku": p.sku,
        "stock": totals.get(p.id, 0), "reorder_point": p.reorder_point
    } for p in products])

@api_bp.post("/sales")
@login_required
def create_sale():
    data = request.json or {}
    items = data.get("items", [])
    pids = [i["product_id"] for i in items]

    # validate products belong to this business
    owned = {p.id for p in Product.query.filter(
        Product.id.in_(pids),
        Product.business_id == current_user.business_id
    ).all()}
    if not set(pids).issubset(owned):
        return jsonify({"error":"One or more items are invalid"}), 400

    sale = Sale(
        user_id=current_user.id,
        business_id=current_user.business_id,
        total_amount=sum(i["qty"]*i["unit_price"] for i in items)
    )
    db.session.add(sale); db.session.flush()

    for it in items:
        db.session.add(SaleItem(sale_id=sale.id, product_id=it["product_id"],
                                qty=it["qty"], unit_price=it["unit_price"]))
        db.session.add(StockMovement(user_id=current_user.id, product_id=it["product_id"],
                                     qty=-abs(it["qty"]), type="OUT", source="sale"))
    db.session.commit()
    return jsonify({"sale_id": sale.id})

@api_bp.get("/sales_list")
@login_required
def sales_list():
    sales = (Sale.query
             .filter_by(business_id=current_user.business_id)
             .options(joinedload(Sale.items).joinedload(SaleItem.product))
             .order_by(Sale.timestamp.desc())
             .limit(int(request.args.get("limit", 50)))
             .all())
    out = []
    for s in sales:
        out.append({
            "id": s.id,
            "timestamp": s.timestamp.isoformat(),
            "total_amount": float(s.total_amount or 0),
            "items": [{
                "product_id": i.product_id,
                "name": (i.product.name if i.product else ""),
                "qty": int(i.qty or 0),
                "unit_price": float(i.unit_price or 0),
            } for i in (s.items or [])]
        })
    return jsonify(out), 200

@api_bp.get("/products")
@login_required
def list_products():
    products = (Product.query
        .filter(Product.business_id == current_user.business_id)
        .order_by(Product.name).all())
    return jsonify([{
        "id": p.id, "sku": p.sku, "name": p.name, "unit": p.unit,
        "barcode": p.barcode, "reorder_point": p.reorder_point,
        "unit_price": p.unit_price,
        "expiry_date": p.expiry_date.isoformat() if p.expiry_date else None,
        "created_at": p.created_at.isoformat() if p.created_at else None
    } for p in products])

@api_bp.post("/products")
@login_required
def create_product():
    data = request.json or {}
    unit_price = float(data.get("unit_price") or 0)
    opening_stock = int(data.get("opening_stock") or 0)
    expiry_date = data.get("expiry_date")

    # per-business SKU uniqueness (soft)
    exists = (Product.query
              .filter_by(business_id=current_user.business_id, sku=data["sku"])
              .first())
    if exists:
        return jsonify({"error":"SKU already exists"}), 400

    p = Product(
        user_id=current_user.id,                          # legacy link
        business_id=current_user.business_id,             # tenant
        sku=data["sku"], name=data["name"],
        category=data.get("category"), unit=data.get("unit","unit"),
        barcode=data.get("barcode"), reorder_point=data.get("reorder_point",0),
        unit_price=unit_price,
        expiry_date=datetime.strptime(expiry_date, "%Y-%m-%d").date() if expiry_date else None,
    )
    db.session.add(p); db.session.flush()

    if opening_stock > 0:
        db.session.add(StockMovement(
            user_id=current_user.id,
            product_id=p.id, qty=opening_stock,
            type="IN", source="opening"
        ))

    db.session.commit()
    return jsonify({"id": p.id}), 201


@api_bp.post("/purchases")
@login_required
def create_purchase():
    data = request.json or {}
    items = data.get("items", [])
    pids = [i["product_id"] for i in items]
    owned = {p.id for p in Product.query.filter(
        Product.id.in_(pids),
        Product.business_id == current_user.business_id
    ).all()}
    if not set(pids).issubset(owned):
        return jsonify({"error":"One or more items are invalid"}), 400

    purchase = Purchase(
        user_id=current_user.id,
        business_id=current_user.business_id,
        total_cost=sum(i["qty"]*i["unit_cost"] for i in items)
    )
    db.session.add(purchase); db.session.flush()
    for it in items:
        db.session.add(PurchaseItem(purchase_id=purchase.id, product_id=it["product_id"],
                                    qty=it["qty"], unit_cost=it["unit_cost"]))
        db.session.add(StockMovement(user_id=current_user.id, product_id=it["product_id"],
                                     qty=abs(it["qty"]), type="IN", source="purchase",
                                     unit_cost=it["unit_cost"]))
    db.session.commit()
    return jsonify({"purchase_id": purchase.id})

@api_bp.get("/activity")
@login_required
def recent_activity():
    limit = int(request.args.get("limit", 10))
    q = (db.session.query(StockMovement, Product)
         .join(Product, StockMovement.product_id == Product.id)
         .filter(Product.business_id == current_user.business_id)
         .order_by(StockMovement.timestamp.desc())
         .limit(limit)
         .all())
    out = []
    for mv, p in q:
        out.append({
            "timestamp": mv.timestamp.isoformat(),
            "sku": p.sku, "name": p.name,
            "type": mv.type, "qty": mv.qty
        })
    return jsonify(out)


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


