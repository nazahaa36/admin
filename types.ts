export interface Member {
  id: string;
  name: string;
  birthDate: string;
  appointmentDate: string;
  expiryDate: string;
  type: 'member' | 'staff';
  barcode: string;
  position?: string;
  cell?: string;
}

export interface AccountingRecord {
  id: string;
  type: 'income' | 'expense';
  category: string;
  amount: number;
  date: string;
  description: string;
}

export interface Activity {
  id: string;
  name: string;
  date: string;
  participants: string[];
}

export interface Attendance {
  id: string;
  activityId: string;
  memberId: string;
  timestamp: number;
}

export interface Document {
  id: string;
  title: string;
  type: string;
  content: string;
  date: string;
}

export interface Notification {
  id: string;
  message: string;
  timestamp: number;
  read: boolean;
}

export interface AppSettings {
  fields: {
    memberName: string;
    memberId: string;
    staffPosition: string;
    staffCell: string;
  };
}
