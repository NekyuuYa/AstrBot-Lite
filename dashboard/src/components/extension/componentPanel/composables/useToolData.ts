import { ref, reactive } from 'vue';
import axios from 'axios';
import type { ToolItem, SnackbarState } from '../types';

export function useToolData() {
  const tools = ref<ToolItem[]>([]);
  const toolsLoading = ref(false);
  const snackbar = reactive<SnackbarState>({
    show: false,
    message: '',
    color: 'success'
  });

  const toast = (message: string, color: string = 'success') => {
    snackbar.message = message;
    snackbar.color = color;
    snackbar.show = true;
  };

  const fetchTools = async (errorMessage: string) => {
    toolsLoading.value = true;
    try {
      const res = await axios.get('/api/tools/list');
      if (res.data.status === 'ok') {
        tools.value = res.data.data || [];
      } else {
        toast(res.data.message || errorMessage, 'error');
      }
    } catch (err: any) {
      toast(err?.message || errorMessage, 'error');
    } finally {
      toolsLoading.value = false;
    }
  };

  return {
    tools,
    toolsLoading,
    snackbar,
    toast,
    fetchTools
  };
}
