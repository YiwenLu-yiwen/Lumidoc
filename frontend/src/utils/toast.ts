import { toast } from 'react-hot-toast';

const shownToasts = new Set<string>();

export const customToast = {
  error: (message: string) => {
    const key = `error-${message}`;
    if (shownToasts.has(key)) {
      return;
    }

    shownToasts.add(key);
    setTimeout(() => shownToasts.delete(key), 3000);
    return toast.error(message);
  }
};
