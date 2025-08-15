import axios from 'axios';
import MockAdapter from 'axios-mock-adapter';

// 创建一个axios实例的模拟适配器
export const mocked = new MockAdapter(axios, { 
  delayResponse: 500,  // 添加500ms延迟，模拟网络延迟
  onNoMatch: 'passthrough'  // 未模拟的请求将被传递到实际的网络请求
});

// 添加通用模拟响应函数
export const mockResponse = <T>(data: T, status: number = 200) => {
  return [status, data];
};

// 添加通用模拟错误函数
export const mockError = (message: string, status: number = 400) => {
  return [status, { detail: message }];
}; 