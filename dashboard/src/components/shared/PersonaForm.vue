<template>
    <v-dialog v-model="showDialog" :max-width="$vuetify.display.smAndDown ? undefined : '1200px'" scrollable>
        <v-card class="persona-form-card" :class="{ 'persona-form-card-mobile': $vuetify.display.smAndDown }">
            <v-card-title class="persona-form-title text-h2 px-6 pt-6 pl-6">
                {{ editingPersona ? tm('dialog.edit.title') : tm('dialog.create.title') }}
            </v-card-title>

            <v-card-text class="persona-form-content">
                <!-- 创建位置提示 -->
                <v-alert v-if="!editingPersona" type="info" variant="tonal" density="compact" class="mb-4"
                    icon="mdi-folder-outline">
                    {{ tm('form.createInFolder', { folder: folderDisplayName }) }}
                </v-alert>

                <v-form ref="personaForm" v-model="formValid">
                    <v-row class="persona-form-layout">
                        <v-col cols="12" md="6" class="persona-basic-col">
                            <v-text-field v-model="personaForm.persona_id" :label="tm('form.personaId')"
                                :rules="personaIdRules" :disabled="editingPersona" variant="outlined"
                                density="comfortable" class="mb-4" />

                            <v-textarea v-model="personaForm.system_prompt" :label="tm('form.systemPrompt')"
                                :rules="systemPromptRules" variant="outlined" rows="16" class="mb-4" />

                            <v-textarea
                                v-model="personaForm.custom_error_message"
                                :label="tm('form.customErrorMessage')"
                                :hint="tm('form.customErrorMessageHelp')"
                                variant="outlined"
                                rows="4"
                                persistent-hint
                                clearable
                                class="mb-4"
                            />
                        </v-col>

                        <v-col cols="12" md="6" class="persona-panels-col">
                            <v-expansion-panels v-model="expandedPanels" multiple>
                        <!-- 预设对话面板 -->
                        <v-expansion-panel value="dialogs">
                            <v-expansion-panel-title>
                                <v-icon class="mr-2">mdi-chat</v-icon>
                                {{ tm('form.presetDialogs') }}
                                <v-chip v-if="personaForm.begin_dialogs.length > 0" size="small" color="primary"
                                    variant="tonal" class="ml-2">
                                    {{ personaForm.begin_dialogs.length / 2 }}
                                </v-chip>
                            </v-expansion-panel-title>

                            <v-expansion-panel-text>
                                <div class="mb-3">
                                    <p class="text-body-2 text-medium-emphasis">
                                        {{ tm('form.presetDialogsHelp') }}
                                    </p>
                                </div>

                                <div v-for="(dialog, index) in personaForm.begin_dialogs" :key="index" class="mb-3">
                                    <v-textarea v-model="personaForm.begin_dialogs[index]"
                                        :label="index % 2 === 0 ? tm('form.userMessage') : tm('form.assistantMessage')"
                                        :rules="getDialogRules(index)" variant="outlined" rows="2"
                                        density="comfortable">
                                        <template v-slot:append>
                                            <v-btn icon="mdi-delete" variant="text" size="small" color="error"
                                                @click="removeDialog(index)" />
                                        </template>
                                    </v-textarea>
                                </div>

                                <v-btn variant="outlined" prepend-icon="mdi-plus" @click="addDialogPair" block>
                                    {{ tm('buttons.addDialogPair') }}
                                </v-btn>
                            </v-expansion-panel-text>
                        </v-expansion-panel>
                            </v-expansion-panels>
                        </v-col>
                    </v-row>
                </v-form>
            </v-card-text>

            <v-card-actions class="persona-form-actions">
                <v-btn v-if="editingPersona" color="error" variant="text" @click="deletePersona">
                    {{ tm('buttons.delete') }}
                </v-btn>
                <v-spacer />
                <v-btn color="grey" variant="text" @click="closeDialog">
                    {{ tm('buttons.cancel') }}
                </v-btn>
                <v-btn color="primary" variant="flat" @click="savePersona" :loading="saving" :disabled="!formValid">
                    {{ tm('buttons.save') }}
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>

<script>
import axios from 'axios';
import { useModuleI18n } from '@/i18n/composables';
import {
    askForConfirmation as askForConfirmationDialog,
    useConfirmDialog
} from '@/utils/confirmDialog';

export default {
    name: 'PersonaForm',
    props: {
        modelValue: {
            type: Boolean,
            default: false
        },
        editingPersona: {
            type: Object,
            default: null
        },
        currentFolderId: {
            type: String,
            default: null
        },
        currentFolderName: {
            type: String,
            default: null
        }
    },
    emits: ['update:modelValue', 'saved', 'error', 'deleted'],
    setup() {
        const { tm } = useModuleI18n('features/persona');
        const confirmDialog = useConfirmDialog();
        return { tm, confirmDialog };
    },
    data() {
        return {
            saving: false,
            expandedPanels: [],
            formValid: false,
            existingPersonaIds: [], // 已存在的人格ID列表
            personaForm: {
                persona_id: '',
                system_prompt: '',
                custom_error_message: '',
                begin_dialogs: [],
                folder_id: null
            },
            personaIdRules: [
                v => !!v || this.tm('validation.required'),
                v => (v && v.length >= 1) || this.tm('validation.minLength', { min: 1 }),
                v => !this.existingPersonaIds.includes(v) || this.tm('validation.personaIdExists'),
            ],
            systemPromptRules: [
                v => !!v || this.tm('validation.required'),
                v => (v && v.length >= 10) || this.tm('validation.minLength', { min: 10 })
            ]
        }
    },

    computed: {
        showDialog: {
            get() {
                return this.modelValue;
            },
            set(value) {
                this.$emit('update:modelValue', value);
            }
        },
        folderDisplayName() {
            // 优先使用传入的文件夹名称
            if (this.currentFolderName) {
                return this.currentFolderName;
            }
            // 如果没有文件夹 ID，显示根目录
            if (!this.currentFolderId) {
                return this.tm('form.rootFolder');
            }
            // 否则显示文件夹 ID（作为备用）
            return this.currentFolderId;
        }
    },

    watch: {
        modelValue(newValue) {
            if (newValue) {
                // 只有在不是编辑状态时才初始化空表单
                if (this.editingPersona) {
                    this.initFormWithPersona(this.editingPersona);
                } else {
                    this.initForm();
                    // 只在创建新人格时加载已存在的人格列表
                    this.loadExistingPersonaIds();
                }
            }
        },
        editingPersona: {
            immediate: true,
            handler(newPersona) {
                // 只有在对话框打开时才处理editingPersona的变化
                if (this.modelValue) {
                    if (newPersona) {
                        this.initFormWithPersona(newPersona);
                    } else {
                        this.initForm();
                    }
                }
            }
        }
    },

    methods: {
        initForm() {
            this.personaForm = {
                persona_id: '',
                system_prompt: '',
                custom_error_message: '',
                begin_dialogs: [],
                folder_id: this.currentFolderId
            };
            this.expandedPanels = this.getDefaultExpandedPanels();
        },

        initFormWithPersona(persona) {
            this.personaForm = {
                persona_id: persona.persona_id,
                system_prompt: persona.system_prompt,
                custom_error_message: persona.custom_error_message || '',
                begin_dialogs: [...(persona.begin_dialogs || [])],
                folder_id: persona.folder_id
            };
            this.expandedPanels = this.getDefaultExpandedPanels();
        },

        getDefaultExpandedPanels() {
            return this.$vuetify.display.smAndDown ? [] : ['dialogs'];
        },

        closeDialog() {
            this.showDialog = false;
        },

        async loadExistingPersonaIds() {
            try {
                const response = await axios.get('/api/persona/list');
                if (response.data.status === 'ok') {
                    this.existingPersonaIds = (response.data.data || []).map(p => p.persona_id);
                }
            } catch (error) {
                // 加载失败不影响表单使用，只是无法进行前端重名校验
                this.existingPersonaIds = [];
            }
        },

        async savePersona() {
            if (!this.formValid) return;

            // 验证预设对话不能为空
            if (this.personaForm.begin_dialogs.length > 0) {
                for (let i = 0; i < this.personaForm.begin_dialogs.length; i++) {
                    if (!this.personaForm.begin_dialogs[i] || this.personaForm.begin_dialogs[i].trim() === '') {
                        const dialogType = i % 2 === 0 ? this.tm('form.userMessage') : this.tm('form.assistantMessage');
                        this.$emit('error', this.tm('validation.dialogRequired', { type: dialogType }));
                        return;
                    }
                }
            }

            this.saving = true;
            try {
                const url = this.editingPersona ? '/api/persona/update' : '/api/persona/create';
                const response = await axios.post(url, this.personaForm);

                if (response.data.status === 'ok') {
                    this.$emit('saved', response.data.message || this.tm('messages.saveSuccess'));
                    this.closeDialog();
                } else {
                    this.$emit('error', response.data.message || this.tm('messages.saveError'));
                }
            } catch (error) {
                this.$emit('error', error.response?.data?.message || this.tm('messages.saveError'));
            }
            this.saving = false;
        },

        async deletePersona() {
            if (!this.editingPersona) return;

            if (
                !(await askForConfirmationDialog(
                    this.tm('messages.deleteConfirm', { id: this.editingPersona.persona_id }),
                    this.confirmDialog,
                ))
            ) {
                return;
            }

            this.saving = true;
            try {
                const response = await axios.post('/api/persona/delete', {
                    persona_id: this.editingPersona.persona_id
                });

                if (response.data.status === 'ok') {
                    this.$emit('deleted', response.data.message || this.tm('messages.deleteSuccess'));
                    this.closeDialog();
                } else {
                    this.$emit('error', response.data.message || this.tm('messages.deleteError'));
                }
            } catch (error) {
                this.$emit('error', error.response?.data?.message || this.tm('messages.deleteError'));
            } finally {
                this.saving = false;
            }
        },

        addDialogPair() {
            this.personaForm.begin_dialogs.push('', '');
            // 自动展开预设对话面板
            if (!this.expandedPanels.includes('dialogs')) {
                this.expandedPanels.push('dialogs');
            }
        },

        removeDialog(index) {
            // 如果是偶数索引（用户消息），删除用户消息和对应的助手消息
            if (index % 2 === 0 && index + 1 < this.personaForm.begin_dialogs.length) {
                this.personaForm.begin_dialogs.splice(index, 2);
            }
            // 如果是奇数索引（助手消息），删除助手消息和对应的用户消息
            else if (index % 2 === 1 && index - 1 >= 0) {
                this.personaForm.begin_dialogs.splice(index - 1, 2);
            }
        },

        getDialogRules(index) {
            const dialogType = index % 2 === 0 ? this.tm('form.userMessage') : this.tm('form.assistantMessage');
            return [
                v => !!v || this.tm('validation.dialogRequired', { type: dialogType }),
                v => (v && v.trim().length > 0) || this.tm('validation.dialogRequired', { type: dialogType })
            ];
        }
    }
}
</script>

<style scoped>
.persona-form-card {
    border-radius: 12px;
    overflow: hidden;
}

.persona-form-content {
    max-height: min(78vh, 760px);
    overflow-y: auto;
}

.persona-form-title {
    line-height: 1.3;
}

.persona-form-actions {
    position: sticky;
    bottom: 0;
    z-index: 2;
    background: rgb(var(--v-theme-surface));
    border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.selected-config-area {
    margin-left: 32px;
}

.persona-form-layout {
    align-items: flex-start;
}

.tools-selection {
    max-height: 300px;
    overflow-y: auto;
}

.skills-selection {
    max-height: 300px;
    overflow-y: auto;
}

.v-virtual-scroll {
    padding-bottom: 16px;
}

@media (max-width: 600px) {
    .persona-form-card-mobile {
        border-radius: 0;
    }

    .persona-form-content {
        max-height: calc(100vh - 128px);
        padding: 16px !important;
    }

    .persona-basic-col,
    .persona-panels-col {
        padding-top: 0 !important;
    }

    .persona-form-title {
        font-size: 1.15rem !important;
        padding: 12px 16px !important;
    }

    .selected-config-area {
        margin-left: 0;
    }

    .tools-selection,
    .skills-selection {
        max-height: 38vh;
    }

    .persona-form-actions {
        padding: 12px 16px !important;
        gap: 8px;
    }

    .persona-form-actions .v-btn {
        min-width: 0;
    }
}
</style>
