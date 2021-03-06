import sys
import os
from PyQt4 import QtCore, QtGui, uic, QtSql

sys.path.insert(0, os.path.split(__file__)[0])

import dbConnection
import report
import functions
from query import query


class Schedule(QtGui.QWidget):
    """
    Schedule
    This is the schedule screen. It is used to generate the schedule for each laser
    """
    updateSchedule = QtCore.pyqtSignal(object)
    schedule_qry = None
    schedule_data = None

    def __init__(self, schedule, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.setWindowTitle("Schedule")
        self.setWindowIcon(QtGui.QIcon(":/icons/production.png"))
        self.setStyleSheet("background-color: rgb(200, 200, 200);")

        self.title = QtGui.QLabel(self)
        self.title.setFont(QtGui.QFont("Terminus", 24, 75, False))
        self.top_layout = QtGui.QHBoxLayout()
        self.top_layout.addWidget(self.title)
        self.top_layout.addStretch(1)

        self.line = QtGui.QFrame(self)
        self.line.setFrameShape(QtGui.QFrame.HLine)
        self.line.setFrameShadow(QtGui.QFrame.Sunken)

        self.scroll = QtGui.QScrollArea(self)
        self.scroll.setFrameShape(QtGui.QFrame.NoFrame)
        self.scroll.setWidgetResizable(True)

        self.schedule_frame = QtGui.QFrame(self.scroll)
        self.schedule_frame.setStyleSheet("background-color: rgb(255, 255, 255);")
        self.schedule_frame.setFrameShape(QtGui.QFrame.StyledPanel)
        self.schedule_frame.setFrameShadow(QtGui.QFrame.Raised)
        self.schedule_layout = QtGui.QVBoxLayout(self.schedule_frame)
        self.schedule_layout.setSpacing(6)
        self.schedule_layout.setContentsMargins(-1, 4, -1, 5)
        self.scroll.setWidget(self.schedule_frame)

        self.layout = QtGui.QVBoxLayout(self)
        self.layout.addLayout(self.top_layout)
        self.layout.addWidget(self.line)
        self.layout.addWidget(self.scroll)

        self.schedule = schedule
        self.setWindowTitle("%s Manager" % self.schedule)
        self.title.setText("%s Manager" % self.schedule)

        #Connect to the update signal
        self.updateSchedule.connect(self.update_schedule_)
        
        #Load all the schedule data from the database
        self.get_schedule_data()
        
    def get_schedule_data(self, qry=None):
        """
        This function retrieved all the required data from the database
        and sends it to the display function. It also sets up a time to check
        for new updates once a second.
        """
        #If qry was passed, use the data from it instead of rerunning the query
        if qry is None:
            self.schedule_qry = query("work_schedule", [self.schedule])
            if not self.schedule_qry:
                return False
        else:
            self.schedule_qry = qry
            self.schedule_qry.seek(-1)
        
        #self.scheduleData is used to check if the schedule needs updated
        self.schedule_data = []
        
        while self.schedule_qry.next():
            row = []
            for i in range(10):
                row.append(self.schedule_qry.value(i))
            self.schedule_data.append(row)
            
            pdf_qry = query("work_order_pdf_check", [self.schedule_qry.value(8).toString()])
            if pdf_qry:
                if pdf_qry.first():
                    has_print = True
                else:
                    has_print = False
            else:
                has_print = False
            
            #Send the data to the display function so it can be added
            #to the layout.
            self.new_row(self.schedule_qry.record(), has_print)
            
        #Pushes all the rows together at the top of the page
        self.schedule_frame.layout().insertStretch(-1)
        
        #Set up update timer. Currently set to update once a second.
        self.startTimer(1000)
        return True
    
    def timerEvent(self, event):
        """
        This function reruns the schedule query and then checks for
        changes in the data. If changes are found, the data is updated.
        """
        qry = query("work_schedule", [self.schedule])
        if qry:
            new_data = []
            #Build a list so it can be compared for differences.
            while qry.next():
                row = []
                for i in range(10):
                    row.append(qry.value(i))
                new_data.append(row)
            if new_data != self.schedule_data:
                #If new data is found, emit the update signal and pass
                #the query so it doesn't have to be reran.
                self.updateSchedule.emit(qry)
                QtGui.QApplication.alert(self)
        else:
            self.killTimer(event.timerId())
            event.ignore()
    
    def update_schedule_(self, qry):
        """
        Called when the schedule needs updated.
        Removes all the current row widgets then calls the schedule data
        function and passes the check query to prevent it from being reran.
        """
        layout = self.schedule_frame.layout()
        functions.clear_layout(layout)
        self.get_schedule_data(qry)
        return
    
    def new_row(self, rec, has_print):
        """
        Lays out the Gui for a new row using the data from rec
        """
        row = functions.NewRow()
        row.priority.setText(rec.value(0).toString().rightJustified(3, QtCore.QChar('0')))
        row.job_number.setText(rec.value(1).toString())
        row.notes.setPlainText(rec.value(9).toString())
        row.material.setText(rec.value(3).toString())
        row.material_qty.setText(rec.value(4).toString())
        row.running = rec.value(5).toString()
        row.finished = rec.value(6).toString()
        row.modifying = rec.value(7).toString()
        row.job = rec.value(8).toString()
        
        row.material.setCompleter(functions.MaterialCompleter())
        
        row.print_report.setEnabled(has_print)
        
        #Sets the different row styles depending on the row status
        row = functions.set_row_style(row)

        row.modified = False
        
        row.print_report.clicked.connect(self.print_report)
        row.hide_job.clicked.connect(self.hide_job_)
        row.edit_job.clicked.connect(self.edit_job_)
        row.upload_pdf.clicked.connect(self.upload_report_)
        
        row.priority.textEdited.connect(self.row_edited)
        row.material.textEdited.connect(self.row_edited)
        row.material_qty.textEdited.connect(self.row_edited)
        
        row.priority.editingFinished.connect(self.row_editing_finished)
        row.material.editingFinished.connect(self.row_editing_finished)
        row.material_qty.editingFinished.connect(self.row_editing_finished)
        
        self.schedule_frame.layout().addWidget(row)
        return
        
    def hide_job_(self):
        """
        Called via signal. Hides the sender row.
        """
        #Find the sender
        job_num = self.sender().parent().job
        
        #Open the connection to the master database server
        dbw, ok = dbConnection.new_connection('write', 'riverview', 'riverview')
        if not ok:
            dbConnection.db_err(dbw)
            return False
        qry = query("finish_work_order", [job_num], dbw)

        #Update the show status to False
        if qry:
            QtGui.QMessageBox.information(self, 'Successful', 'Job %s has been hidden' % job_num)
            return True
        else:
            return False

    def edit_job_(self):
        """
        Called via signal. Marks the sender row as being modified.
        """
        #Find the sender
        job_num = self.sender().parent().job
        
        #Open the connection to the master database server
        dbw, ok = dbConnection.new_connection('write', 'riverview', 'riverview')
        if not ok:
            dbConnection.db_err(dbw)
            return False
        qry = query("modify_work_order", [job_num], dbw)
        if qry:
            QtGui.QMessageBox.information(self, 'Successful', 'The edit status for Job %s as been changed' % job_num)
            return True
        else:
            return False

    def row_edited(self):
        """
        Marks the current row as red if it has been modified
        """
        #Find the sender
        row = self.sender().parent()
        row.setStyleSheet('background-color:rgb(200,40,40);')
    
    def row_editing_finished(self):
        """
        Saves the current row data to the database
        """
        #Find the sender
        row = self.sender().parent()
        data = [row.job, row.priority.text(), 
                row.material.text(), row.material_qty.text()]
        dbw, ok = dbConnection.new_connection('write', 'riverview', 'riverview')
        if ok:
            qry = query("update_work_order", data, dbw)
            if qry:
                row.setStyleSheet('')
    
    def upload_report_(self):
        """
        Function for uploading a pdf to the database so the user can
        print it from their scheduler.
        """
        #Find the sender
        job_num = self.sender().parent().job
        
        #Get the last directory that was used
        last_laser = str(functions.read_settings('last_laser').toString())
        
        #Get the report_file the user wants to upload
        report_file = QtGui.QFileDialog.getOpenFileName(self, caption='Open Print', filter='*.pdf',
                                                        directory=last_laser)
        if report_file:
            functions.write_settings('last_laser', last_laser.rsplit('/', 1)[0])
            print_bin = open(report_file, 'rb')
            dbw, ok = dbConnection.new_connection('write', 'riverview', 'riverview')
            if ok:
                qry = query("insert_pdf", [job_num, print_bin.read().encode('hex')], dbw)
                if qry:
                    QtGui.QMessageBox.information(None, "Successful", "Paperwork Successfully uploaded")
                    self.update_schedule_(None)
                    return True
                else:
                    return False

    def print_report(self):
        """
        Creates/downloads and opens pdf files of the paperwork needed to
        run the sender job.
        
        The part routers are created and the laser sheets are downloaded
        """
        job_num = self.sender().parent().job
        qry = query("get_pdf", [job_num])
        if qry:
            if qry.first():
                pdf_file = '.tmp.pdf'
                with open(pdf_file, 'wb') as f:
                    pdf = qry.value(0).toByteArray()
                    #Write the laser sheet to tmp.pdf
                    f.write(pdf)
                    f.close()
            
                #Determine the correct platform and open the laser sheet
                if sys.platform.startswith('darwin'):
                    os.system('open %s' % pdf_file)
                elif sys.platform.startswith('linux'):
                    os.system('xdg-open %s' % pdf_file)
                elif sys.platform.startswith('win32'):
                    os.startfile('%s' % pdf_file)
            else:
                text = ("No pdf file for the current job could be found in the database. "
                        "If you require one please contact the scheduler."
                        )
                QtGui.QMessageBox.information(self, "No File", text)
        else:
            return False
        
        qry = query("report_header_data", [job_num])
        if qry:
            qry.first()
            h_data = [qry.value(0).toString(), qry.value(1).toString(), qry.value(2).toString(), ]
        else:
            return False

        #Get the individual part information
        qry = query("report_data", [job_num])
        if qry:
            rows = qry.size()
            row_data = []
            while qry.next():
                row_data.append(qry.record())
        else:
            return False
        
        #Get local print location
        prints = functions.read_settings('prints').toString()
        #If the location isn't in the settings file, ask for it then save it.
        if not prints:
            prints = QtGui.QFileDialog.getExistingDirectory(self, 'Prints')
            if prints:
                functions.write_settings('prints', prints)
            else:
                text = "Prints location couldn't be determined."
                QtGui.QMessageBox.critical(self, "Error", text)
                return False
                
        #Generate and save the report to pdf
        report.ind_wo(h_data, rows, row_data, prints)
        
        #Locate and open the report
        pdf_file = "indWo.pdf"
        if sys.platform.startswith('darwin'):
            os.system('open %s' % pdf_file)
        elif sys.platform.startswith('linux'):
            os.system('xdg-open %s' % pdf_file)
        elif sys.platform.startswith('win32'):
            os.startfile('%s' % pdf_file)
        return True