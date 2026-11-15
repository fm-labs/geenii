
export const restoreSidebarOpenState = (): boolean => {
  return localStorage.getItem("xchat.sidebar.open") === "true";
}

export const storeSidebarOpenState = (newState: boolean) => {
  localStorage.setItem("xchat.sidebar.open", newState ? "true" : "false");
}
