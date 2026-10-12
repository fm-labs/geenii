import { toast } from 'react-toastify'

type NotificationType = 'default' | 'success' | 'error' | 'info' | 'warning' ;

interface NotificationHandlerInterface {
  handleMessage: (message: string, type?: NotificationType) => void;
}

class ConsoleNotificationHandler implements NotificationHandlerInterface {
  handleMessage(message: string, type: NotificationType = 'default') {
    // Logic to display notification
    console.log(`Console Notification: ${message}, Type: ${type}`);
  }
}

class AlertNotificationHandler implements NotificationHandlerInterface {
  handleMessage(message: string, type: NotificationType = 'default') {
    // Logic to display notification
    alert(`Alert Notification: ${message}, Type: ${type}`);
  }
}

class ToastNotificationHandler implements NotificationHandlerInterface {
  handleMessage(message: string, type: NotificationType = 'default') {
    // Logic to display notification
    // Assuming a toast library is used, e.g., react-toastify
    console.log(`Toast Notification: ${message}, Type: ${type}`);
    toast(message, { type });
  }
}


const useNotification = () => {

  const notificationHandler: NotificationHandlerInterface = new ToastNotificationHandler();

  const send = (message: string, type: NotificationType = 'default') => {
    // Logic to display notification
    console.log(`Notification: ${message}, Type: ${type}`);
    notificationHandler.handleMessage(message, type);
  };

  const success = (message: string) => {
    send(message, 'success');
  }

  const error = (message: string) => {
    send(message, 'error');
  }

  const info = (message: string) => {
    send(message, 'info');
  }

  const warning = (message: string) => {
    send(message, 'warning');
  }

  return {
    send: send,
    success: success,
    error: error,
    info: info,
    warning: warning
  };
}

export default useNotification;
