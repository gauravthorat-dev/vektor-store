## 🌐 Live Demo
Coming Soon (Deployment in progress)

---

# Vektor Store 🛍️

> 🚀 Vektor Store is a full-stack e-commerce platform built with Flask, featuring complete shopping flow, admin panel, and analytics dashboard.

It simulates a real-world production system with modular backend architecture and dynamic UI.
---

## 🚀 Features

- Product listing with filters (price, size, category)
- Product detail page with size & color selection
- Add to cart functionality
- Checkout system (Cash on Delivery / UPI)
- User dashboard with order tracking
- Admin panel for product & order management
- Analytics dashboard for business insights

---

## 🔌 Key Functionalities

- REST-style routing using Flask
- Cart and session management
- Order processing system
- Role-based admin control
- Real-time analytics dashboard

---

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python (Flask) |
| Database | MySQL |
| Frontend | HTML, CSS, JavaScript |
| Version Control | Git & GitHub |

---

## 📁 Project Structure
app.py
routes/
models/
services/
templates/
static/
database/
migrations/

---

## ▶️ How to Run

### 1. Clone the repository
```bash
git clone https://github.com/gauravthorat-dev/vektor-store.git
cd vektor-store
```

### 2. Create and activate virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

- Copy `.env.example` to `.env`
- Update values like database URL, secret key

```bash
# Windows
copy .env.example .env

# Mac/Linux
cp .env.example .env
```

### 5. Run the application

```bash
python app.py
```

### 6. Open in browser
http://127.0.0.1:5000/

---


## 📸 Screenshots

### 🏠 Homepage
![Homepage](./newhomepage.png)

### 🛍️ Product Listing
![Product Listing](./newproductpage.png)

### 📦 Product Detail
![Product Detail](./newviewproductpage.png)

### 🛒 Cart Page
![Cart](./newcartpage.png)

### 📊 Admin Dashboard
![Admin Dashboard](./admindashbordpage.png)
---

## ⚠️ Note

This is a **demo version** of the project. Full production code is kept private.

---

## 📄 License

This project is protected under a custom license. Unauthorized use is not allowed.

---

## 👨‍💻 Author

**Gaurav Thorat**

[![GitHub](https://img.shields.io/badge/GitHub-gauravthorat--dev-181717?style=flat&logo=github)](https://github.com/gauravthorat-dev)
