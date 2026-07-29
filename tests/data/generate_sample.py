from reportlab.pdfgen import canvas

c = canvas.Canvas("sample_resume.pdf")
c.drawString(100, 750, "John Doe")
c.drawString(100, 730, "Skills: Python, Machine Learning, FastAPI")
c.drawString(100, 710, "Experience: AI Intern")
c.save()
