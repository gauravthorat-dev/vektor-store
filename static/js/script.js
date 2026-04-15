// ================= GLOBAL VARIABLES =================
let count = 0; // cart item count

// ================= PAGE LOAD =================
window.addEventListener("load", function () {

    // ===== CART SYSTEM =====
    const buttons = document.querySelectorAll(".product-card button");
    const cartCount = document.getElementById("cart-count");

    buttons.forEach(button => {
        button.addEventListener("click", function () {
            count++; // increase cart count
            if(cartCount){
                cartCount.innerText = count; // update UI
            }
        });
    });

    // ===== PRELOADER REMOVE =====
    const preloader = document.getElementById("preloader");

    if(preloader){
        setTimeout(() => {
            preloader.style.opacity = "0";
            setTimeout(()=> preloader.style.display = "none", 500);
        }, 800);
    }

    // ===== START TYPING EFFECT =====
    typing();

});


// ================= TYPING EFFECT =================
const text = "FashionHub";
let i = 0;

function typing(){
    if(i < text.length){
        document.getElementById("typing-text").innerHTML += text.charAt(i);
        i++;
        setTimeout(typing, 100);
    }
}


// ================= SCROLL REVEAL (PRODUCT CARDS) =================
window.addEventListener("scroll", function(){

    const cards = document.querySelectorAll(".product-card");
    const trigger = window.innerHeight * 0.85;

    cards.forEach(card => {

        const top = card.getBoundingClientRect().top;

        // ✅ Show only once (no remove → no disappearing bug)
        if(top < trigger){
            card.classList.add("show");
        }

    });

});


// ================= SHIRT TRY-ON =================
function changeShirt(src){
    const shirt = document.getElementById("shirtOverlay");

    if(shirt){
        shirt.src = src;          // change image
        shirt.style.display = "block"; // show shirt
    }
}


// ================= PAYMENT METHOD =================
function setPaymentMethod(){
    const payMethod = document.getElementById("payMethod");

    if(typeof order !== "undefined" && payMethod){
        payMethod.innerText = order.payment || "Cash on Delivery";
    }
}


// ================= COUPON SYSTEM =================
function applyCoupon(){

    const couponInput = document.getElementById("couponInput");
    const ototal = document.getElementById("ototal");

    if(!couponInput || !ototal || typeof order === "undefined") return;

    let code = couponInput.value.trim().toUpperCase();

    if(code === "SAVE10"){
        let discount = order.total * 0.10;
        let newTotal = order.total - discount;
        ototal.innerText = newTotal.toLocaleString();
        alert("🎉 Coupon Applied! 10% discount");
    }
    else if(code === "FASHION20"){
        let discount = order.total * 0.20;
        let newTotal = order.total - discount;
        ototal.innerText = newTotal.toLocaleString();
        alert("🔥 20% Mega Discount Applied!");
    }
    else{
        alert("❌ Invalid Coupon Code");
    }
}


// ================= CANCEL ORDER =================
function cancelOrder(){

    if(typeof order === "undefined") return;

    if(order.status === "Shipped" || order.status === "Delivered"){
        alert("❌ Order cannot be cancelled now.");
        return;
    }

    if(confirm("Are you sure you want to cancel this order?")){
        order.status = "Cancelled";
        localStorage.setItem("orders", JSON.stringify(orders));
        alert("Order Cancelled Successfully");
        location.reload();
    }
}


// ================= GOLD PARTICLES BACKGROUND =================
const canvas = document.getElementById("particles");

if(canvas){

    const ctx = canvas.getContext("2d");

    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    let particles = [];

    for(let i = 0; i < 70; i++){
        particles.push({
            x: Math.random()*canvas.width,
            y: Math.random()*canvas.height,
            r: Math.random()*2 + 1,
            d: Math.random()*1
        });
    }

    function drawParticles(){

        ctx.clearRect(0,0,canvas.width,canvas.height);
        ctx.fillStyle = "rgba(212,175,55,0.2)";

        particles.forEach(p => {
            ctx.beginPath();
            ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
            ctx.fill();

            p.y += p.d;

            if(p.y > canvas.height){
                p.y = 0;
            }
        });

        requestAnimationFrame(drawParticles);
    }

    drawParticles();
}


// ================= DUST EFFECT =================
const dustCanvas = document.getElementById("dust");

if(dustCanvas){

    const ctx = dustCanvas.getContext("2d");

    dustCanvas.width = window.innerWidth;
    dustCanvas.height = window.innerHeight;

    let dust = [];

    for(let i = 0; i < 60; i++){
        dust.push({
            x: Math.random()*dustCanvas.width,
            y: Math.random()*dustCanvas.height,
            r: Math.random()*2 + 1,
            s: Math.random()*0.6
        });
    }

    function animateDust(){

        ctx.clearRect(0,0,dustCanvas.width,dustCanvas.height);
        ctx.fillStyle = "rgba(255,255,255,0.15)";

        dust.forEach(p => {
            ctx.beginPath();
            ctx.arc(p.x,p.y,p.r,0,6.28);
            ctx.fill();

            p.y -= p.s;

            if(p.y < 0){
                p.y = dustCanvas.height;
            }
        });

        requestAnimationFrame(animateDust);
    }

    animateDust();
}


// ================= HERO PARALLAX =================
document.addEventListener("mousemove", function(e){

    const hero = document.querySelector(".hero-content");

    if(hero){
        let x = (window.innerWidth/2 - e.pageX)/90;
        let y = (window.innerHeight/2 - e.pageY)/90;

        hero.style.transform = `translate(${x}px,${y}px)`;
    }
});


// ================= MAGNETIC BUTTON EFFECT =================
const magneticButtons = document.querySelectorAll(".hero-btn, .btn");

magneticButtons.forEach(el => {

    el.addEventListener("mousemove", e => {

        const rect = el.getBoundingClientRect();

        const x = e.clientX - rect.left - rect.width / 2;
        const y = e.clientY - rect.top - rect.height / 2;

        el.style.transform = `translate(${x * 0.2}px, ${y * 0.2}px)`;
    });

    el.addEventListener("mouseleave", () => {
        el.style.transform = "translate(0,0)";
    });

});


// ================= LOGOUT MODAL AUTO CLOSE =================
setTimeout(function(){

    let modal = document.getElementById("logoutModal");

    if(modal){
        modal.style.opacity = "0";

        setTimeout(function(){
            modal.style.display = "none";
        },400);
    }

},2000);