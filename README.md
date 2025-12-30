# BJJ Gym CRM

## Distinctiveness and Complexity

This project provides a **CRM solution specifically designed for a Brazilian Jiu-Jitsu (BJJ) gym**. It aims to streamline the management of students, staff, classes, attendance, and finances in a real BJJ studio setting.
The main motivation for developing this system comes from real-world experience: since opening my own studio in May 2025, one of the most challenging aspects of the business has been keeping all essential information in one place. Using spreadsheets or notebooks proved inefficient, making it difficult to keep and access the right information when needed.

A web-based application solves this problem by making the system available anywhere — whether at the local front desk or on a personal smartphone.  

Tracking student consistency is a critical part of the process, as their improvement and subsequent promotions depend on regular attendance. Additionally, tracking promotions ensures that IBJJF (International Brazilian Jiu-Jitsu Federation) rules are followed accurately.

By focusing on the unique needs of a martial arts gym, this CRM system stands out from general-purpose CRM applications. It is designed to be **distinctive and complex enough** to address the specific business requirements of a BJJ academy.

---

## Features

The application includes the following core functionalities:

- **User Registration**  
  Register new students, with personal information
  - ability of registering multiple contact person.
  - ability to resgister multiple responsible person (for kids).
  
- **Coach/Staff Registration** 
  Register new staff, and coaches with personal and professional details.


- **Subscription Management**  
  Students can fill, edit, and manage their subscription plans autonomously.

- **Class Registration**  
  Staff can create and manage all types of classes.

- **Class Schedule**  
  View daily schedules of all available classes.

- **Attendance Tracking**  
  Students can report their attendance.  
  *Future version:* integration with a face recognition system for automated attendance.

- **Promotion System**  
  Track student progression through BJJ belts and stripes.

- **Dashboard**  
  Provides useful analytics and visualizations of gym activities and performance.


---

## Technology Stack

- **Backend:** Django / Python  
- **Frontend:** HTML, CSS, JavaScript (Bootstrap 5)  
- **Database:** PostgreSQL / SQLite (configurable)  
- **Other:** Font Awesome, AJAX for dynamic features

---

## Installation

1. Clone the repository:

git clone (https://github.com/me50/renatomac.git)
cd bjj-gym-crm

2. Create a virtual environment and activate it:
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

3. Install dependencies:
pip install -r requirements.txt

4. Run migrations:
python manage.py migrate

5. Start the development server:
python manage.py runserver

6. Open your browser and navegate to http://127.0.0.1:8000/.

## Usage

- Register new students.

- Register new staff or coaches.

- Create/Edit classes.

- Create/Edit schedules.

- Create/Edit Memebership plans.

- Store and visualize the students information.

- Track the number of active and inactive students.

- Track attendance for each class.

- Update student promotions.

## Future Enhancements

- **Face recognition** system for automated attendance tracking.

- **Analytics** Advanced reporting and analytics for student performance.

- **Payment Integration** Integration with payment gateways for automatic subscription handling.

- **Payment Integration** Integration with payment gateways for automatic subscription handling.

- **Financial Tracking**  Monitor the gym’s business evolution, including subscriptions, revenue, and other metrics.

- **Monitor financial** and operational metrics through the dashboard.
