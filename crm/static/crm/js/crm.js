// ADD CONTACT TO MEMBERS
console.log("crm.js loaded");

function getCSRFToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]").value;
}

document.addEventListener("click", function (event) {
    const button = event.target.closest(".techBtn");
    if (!button) return;

    
    const techSelect = document.getElementById("techSelect");
    const selectedValues = Array.from(techSelect.selectedOptions).map(option => option.value);
    const techComment = document.getElementById("comment-id").value;
    if (selectedValues.length === 0 && techComment == " "){
        console.log("No data to save.")
        return;
    }

    if (selectedValues.length === 0){
        console.log("no techinique selected.")
    }

    if (techComment === " "){
        console.log("Add a comment")
    }

    const payload = {
        session_date: document.getElementById("sessionDate").value,
        session_id: document.getElementById("sessionSelect").value,
        technique_id: selectedValues,
        comment: document.getElementById("comment-id").value,
    };

    // Best practice to create the URL correctly
    const url = button.dataset.saveUrl;

    fetch("/saveTechnique", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCSRFToken()
        },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        console.log(data)
        location.reload();
    });
});




document.addEventListener("DOMContentLoaded", function () {
    const date = document.getElementById("sessionDate");
    const sel = document.getElementById("sessionSelect");
    if (!date || !sel) return;

    // --- Helper: 24h "HH:MM:SS" -> "h:mm a.m./p.m." ---
    function formatTime24to12(timeStr) {
        // Accepts "18:30:00" or "06:05:00" or "18:30"
        if (!timeStr) return "";
        const [h, m] = timeStr.split(":");
        const hour = Number(h);
        const ampm = hour >= 12 ? "p.m." : "a.m.";
        const hour12 = ((hour + 11) % 12) + 1; // 0->12, 13->1, etc.
        return `${hour12}:${String(m).padStart(2, "0")} ${ampm}`;
    }

    
    date.addEventListener('change', dateSelect);
    function dateSelect(){
        const url = new URL(`/getSessionsByDate/${date.value}`, window.location.origin);
        fetch(url)
        .then(response => response.json())
        .then(data => {
            while (sel.options.length > 1) {    
                sel.remove(1);
            }
            for (const option of sel.options) {
                option.selected = option.value === "Select Class";
            }
            data.forEach(session => {
            const option = document.createElement("option");
            
            option.value = session.id;
            const start = formatTime24to12(session.start_time);
            option.textContent = `${session.class_template__name} (${start})`;
            sel.appendChild(option);
            });
        });
    }

    sel.addEventListener('change', sessionSelect);
    function sessionSelect(){
        const sessionId = this.value;
        if (!sessionId || sessionId == 0) return;

        // keep selected date if present
        const dateInput = document.getElementById("sessionDate");
        const dateParam = dateInput?.value
            ? `?classDate=${dateInput.value}`
            : "";

        window.location.href = `/attendanceRecord/${sessionId}/${dateParam}`;
    }
});


document.addEventListener("DOMContentLoaded", function () {
    let sel = document.getElementById("id_new_rank");
    if (!sel) return;
    
    sel.addEventListener('change', beltUpdate);

    function beltUpdate(){
        document.getElementById("id_new_stripes").value = 0;

        const temp = document.createElement("div"); 
         
        let belt= sel.value+"-belt";
        belt=belt.replaceAll(/_/g, "-");
        temp.className = belt;
        document.body.appendChild(temp);
        const styles = getComputedStyle(temp);
        const bg = styles.getPropertyValue("--belt-bg").trim();
        const color = styles.getPropertyValue("--belt-color").trim();

        
        let nbDiv = document.getElementById("id_new_rank_div")
        nbDiv.classList.forEach(c => {
            if (c.endsWith("-belt")) nbDiv.classList.remove(c);
            });
        nbDiv.classList.add(belt);

        const beltName = styles
        .getPropertyValue("--belt-name")
        .replace(/"/g, "")
        .trim();

        
        let dflex = nbDiv.querySelector(".d-flex");
        let text = dflex.querySelector(".fw-semibold");
        if (text) {
            text.textContent = beltName;
        }
        document.body.removeChild(temp);
    }
    

})


document.addEventListener("DOMContentLoaded", function () {
    let sel = document.getElementById("id_new_stripes");
    if (!sel) return;
    console.log(sel.value);
    sel.addEventListener('change', beltStripes);
    function beltStripes(){
        const temp = document.createElement("div"); 
        let stripes = sel.value;

        let nbDiv = document.getElementById("id_new_rank_div")
        let dflex = nbDiv.querySelector(".d-flex");
        let text = dflex.querySelector(".fw-semibold").innerHTML;
        
        while(text.endsWith("●")){
            text = text.replace("●", "")
        }
        text += " "
        for(let x=0;x<stripes;x++){
            text += "●"
        }
        dflex.querySelector(".fw-semibold").innerHTML = text;

        console.log(text)
    }
});


document.addEventListener("click", function (event) {
    const button = event.target.closest(".toggle-status");
    if (!button) return;

    const memberId = button.dataset.id;
    const type = button.dataset.type;

    fetch(`/toggleStatus/${type}/${memberId}`)
        .then(response => response.json())
        .then(data => {
            location.reload();
        });
});

function updateBtn(status){
    const toggleBtn = document.getElementById("toggle-status");
    const toggleImg = document.getElementById("toggle-img");

    toggleBtn.classList.remove('btn-outline-danger', 'btn-outline-success');
    toggleImg.classList.remove("fa-user-slash", "fa-user-plus");

    if(status === true){
        //console.log(true);
        toggleBtn.classList.add('btn-outline-success');
        toggleImg.classList.add('fa-user-plus');
    }
    else{
        //console.log(false);
        toggleBtn.classList.add('btn-outline-danger');
        toggleImg.classList.add('fa-user-slash');
    }
}


// FILL THE RESPONSIBLE TAB OF THE MEMBER VIEW WITH ALL CONTACT INFORMATION
document.addEventListener("DOMContentLoaded", function () {
    const responsible = document.getElementById("responsible-tab");
    
    if (responsible) {
         responsible.addEventListener("shown.bs.tab", function () {
            tab = document.getElementById("responsible-contacts" ); 
            const url = new URL(`/getContacts/${tab.dataset.memberId}`, window.location.origin);
            url.searchParams.append("filter", 'responsible');
            fetch(url)
                .then(response => response.json())
                .then(data => {
                    console.log(data.contacts)  
                    let contacts = data.contacts;
                    tab.replaceChildren();
                    if (!contacts.length) {
                        tab.textContent = "No responsible contacts found.";
                    }
                    for(let i=0; i < contacts.length;i++){
                        tab.insertAdjacentHTML("beforeend", createResponsibleHTML(contacts[i]));
                    }
                });
         });
    }
});

// FILL THE emergency TAB OF THE MEMBER VIEW WITH ALL CONTACT INFORMATION
document.addEventListener("DOMContentLoaded", function () {
    const emergency = document.getElementById("emergency-tab");
    
    if (emergency) {
         emergency.addEventListener("shown.bs.tab", function () {
            tab = document.getElementById("emergency-contacts" ); 
            const url = new URL(`/getContacts/${tab.dataset.memberId}`, window.location.origin);
            url.searchParams.append("filter", 'emergency');
            fetch(url)
                .then(response => response.json())
                .then(data => {
                    console.log(data.contacts)
                    let contacts = data.contacts;
                    tab.replaceChildren();
                    if (!contacts.length) {
                        tab.textContent = "No emergency contacts found.";
                    }
                    for(let i=0; i < contacts.length;i++){
                        tab.insertAdjacentHTML("beforeend", createResponsibleHTML(contacts[i]));
                    }
                });
         });
    }
});

function createResponsibleHTML(r) {
    return `
      <div class="container-fluid border text-bg-light mt-3 row">
        <div class="col-md-4">
          <strong>Name:</strong>
          <p class="text-secondary">${r.name ?? "—"}</p>
        </div>
        <div class="col-md-4">
          <strong>Phone:</strong>
          <p class="text-secondary">${r.phone ?? "—"}</p>
        </div>
        <div class="col-md-4">
          <strong>E-mail:</strong>
          <p class="text-secondary">${r.email ?? "—"}</p>
        </div>
        <div class="col-md-4">
          <strong>Relationship:</strong>
          <p class="text-secondary">${r.relationship ?? "—"}</p>
        </div>
      </div>
    `;
}


/*
function getContacts(member_id, filter){
    const url = new URL(`/getContacts/${member_id}`, window.location.origin);
    if (filter) {
        url.searchParams.append("filter", filter);
    }
    fetch('/getContacts/'+ member_id)
        .then(response => response.json())
        .then(data => {
            let contacts = data.contacts;
            for(let i=0; i < contacts.length;i++){

            }
        });
    
}
       

function getClasses(value) {
    classSelect = document.getElementById("classSelect");
    fetch('/getClasses/'+ value)
        .then(response => response.json())
        .then(data => {
            classSelect.options.length = 0;
            var z = document.createElement("option");
            var t = document.createTextNode("Select a Class" );
            z.append(t);
            classSelect.append(z);
            for (i=0;i<data.length;i++){
                console.log(data[i].name)
                var z = document.createElement("option");
                z.setAttribute("value", data[i].id);
                var t = document.createTextNode(data[i].name + " (" + data[i].start_time.slice(0,5) + ")" );
                z.append(t);
                classSelect.append(z);
            }
            }
        );
}

*/


function getStudents(value) {
    classDate = document.getElementById("classDate").value;
    classSelect = document.getElementById("classSelect");
    fetch(`/getStudents/${value}`)
        .then(response => response.json())
        .then(data => {
            students = document.getElementById("students");
            students.replaceChildren();
            if (data.length > 0){
                total = data.length
                checked = 0
                console.log(total)
                let div = document.createElement("div");
                div.setAttribute("id","roster");
                div.setAttribute("class","d-grid gap-3");
                students.append(div);
                let table = document.createElement("table");
                table.setAttribute("class","table table-hover align-middle mb-0");
                div.append(table);
                let tbody = document.createElement("tbody");
                table.append(tbody)
                //for (let i=0;i<data.length;i++){
                data.forEach((item, x) => {
                    
                    let tr = document.createElement("tr");
                    tbody.append(tr)
                    let td = document.createElement("td");
                    tr.append(td)
                    let div2 = document.createElement("div");
                    div2.setAttribute("class","d-flex align-items-center");
                    td.append(div2);
                    let i = document.createElement("i");
                    i.setAttribute("class","fas fa-user-circle me-2 text-secondary h4 mb-0");
                    div2.append(i);
                    div3 = document.createElement("div");
                    div2.append(div3)
                    let a = document.createElement("a");
                    a.href = `/members/${item.id}/`;
                    a.setAttribute("class","text-dark fw-bold text-decoration-none");
                    a.innerHTML = item.first_name + " " + item.last_name ;
                    div3.append(a)
                    let p = document.createElement("p");
                    p.setAttribute("class","small text-muted" )
                    p.innerHTML=  item.belt_rank ;
                    div3.append(p);
                    let td2 = document.createElement("td");
                    tr.append(td2);
                    let span2 = document.createElement("span");
                    span2.setAttribute("id", "span"+item.id)
                    
                    let i2 = document.createElement("i");
                    i2.setAttribute("id", "i"+item.id)

                    if (item.present === true){
                        checked = checked+1;
                        span2.setAttribute("class","badge rounded-pill bg-success");
                        i2.setAttribute("class", "fas fa-user-check me-1");
                        i2.innerHTML = "Checked-in";
                    }
                    else{
                        span2.setAttribute("class","badge rounded-pill bg-secondary");
                        i2.setAttribute("class","fas fa-exclamation-circle me-1");
                        i2.innerHTML = "Not checked-in";
                    }
                    td2.append(span2);
                    span2.append(i2)

                    let td3 = document.createElement("td");
                    tr.append(td3);
                    let btn = document.createElement("button");
                    btn.setAttribute("id", "toggle-attendance"+item.id)
                    btn.setAttribute("class","toggle-attendance");
                    btn.dataset.memberId = item.id;
                    
                    let i4 = document.createElement("i");
                    i4.setAttribute("id", "btn_i"+item.id)
                    if (item.present === true){
                        btn.setAttribute("class", "btn btn-outline-secondary btn-sm toggle-attendance")
                        //i4.setAttribute("class", "fa-solid fa-rotate-left me-1")
                        //i4.classList.remove("fa-user-check"); 
                        //i4.setAttribute("class","fa-solid fa-rotate-left me-1");
                        btn.innerHTML = "Undo"
                    }
                    else{
                        btn.setAttribute("class", "btn btn-outline-secondary btn-sm toggle-attendance")
                        //btn.setAttribute("data-toggle", item.id);                        
                        //i4.setAttribute("class","fa-solid fa-user-check me-1");
                        //i4.classList.remove("fa-rotate-left")
                        btn.innerHTML = "Check-in";
                    }
                    
                    
                    btn.append(i4);
                    td3.append(btn);
                    /*
                    let td4 = document.createElement("td");
                    tr.append(td4);
                    let btn2 = document.createElement("button");
                    btn2.setAttribute("class", "btn btn-outline-danger btn-sm")
                    btn2.setAttribute("data-delete", item.id);
                    let i5 = document.createElement("i");
                    i5.setAttribute("class","fa-solid fa-user-minus");
                    btn2.append(i5);
                    td4.append(btn2);
                    */
                })
                document.getElementById('countTotal').innerHTML = total
                document.getElementById('countChecked').innerHTML = checked
            }
                
            else{
                console.log(" No student selected. ")    
            }
        });
}

document.addEventListener("click", function (event) {
    const btn = event.target.closest(".toggle-attendance");
    if (!btn) return;

    const attendeeId = btn.dataset.attendeeId; 
    console.log(attendeeId)
        
    const url = `/toggleAttendance/${attendeeId}`;
    fetch(url)
        .then(response => response.json())
        .then(data => {
            const span = document.getElementById('span'+attendeeId);
            const i = document.getElementById('i'+attendeeId);
            const label = document.getElementById('label'+attendeeId);
            const labelBtn = document.getElementById('labelBtn'+attendeeId);
            const btn_i = document.getElementById('btn_i'+attendeeId);
            const total = document.getElementById('countTotal').innerHTML
            const checked = document.getElementById('countChecked').innerHTML
            let checkedInt = parseInt(checked, 10);

            if(data.status === 'created'){
                span.classList.replace("bg-secondary", "bg-success");
                label.textContent = "Checked-in";
                if (i.classList.contains("fa-circle-exclamation")) {
                    i.classList.replace("fa-circle-exclamation", "fa-circle-check");
                }
                
                
                labelBtn.textContent = " Undo";
                checkedInt = checkedInt+1
                btn_i.classList.remove("fa-user-check");
                btn_i.classList.add("fa-solid");
                btn_i.classList.add("fa-rotate-left");

            }
            else if(data.status === 'deleted'){
                span.classList.replace("bg-success", "bg-secondary");
                const label = span.querySelector(".label-text");
                label.textContent = "Not checked-in";

                if (i.classList.contains("fa-circle-check")) {
                    i.classList.replace("fa-circle-check", "fa-circle-exclamation");
                }
                
                labelBtn.textContent = " Check-in";
                checkedInt = checkedInt-1
                btn_i.classList.remove("fa-rotate-left");
                btn_i.classList.add("fa-solid");
                btn_i.classList.add("fa-user-check");
            }
            document.getElementById('countChecked').innerHTML = checkedInt
        });
});


// Auto-submit when any select changes
document.querySelectorAll(".filter-input").forEach(function(el) {
    el.addEventListener("change", function() {
        document.getElementById("filterForm").submit();
    });
});






