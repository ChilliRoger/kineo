"""
gemini_audio_session.py
Alternative implementation using Gemini's standard audio API
Since Live API is not available, this uses generate_content with audio input/output
"""

import asyncio
import base64
import json
import os
from typing import Optional, Callable
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Import tools
from tools.firestore_client import get_customer, save_session_log
from tools.churn_scorer import score_churn

load_dotenv()

class GeminiAudioSession:
    """
    Manages audio interaction with Gemini using standard API.
    Simulates bidirectional audio conversation.
    """
    
    def __init__(self, customer_id: str, session_id: str):
        """Initialize Gemini audio session"""
        self.customer_id = customer_id
        self.session_id = session_id
        self.client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        self.model_id = 'gemini-2.0-flash'  # Try 2.0 flash - might have separate quota
        
        # Session state
        self.is_active = False
        self.customer_data = None
        self.conversation_history = []
        self.audio_buffer = []
        self.detected_language = "en"  # Default to English
        self.language_detected = False  # Flag to track if language has been detected
        
        # Callbacks
        self.on_audio_response: Optional[Callable] = None
        self.on_text_response: Optional[Callable] = None
        self.on_tool_call: Optional[Callable] = None
        
        # System prompt (will be updated with language context)
        self.system_prompt = self._create_system_prompt()
        
        print(f"✅ GeminiAudioSession created: {session_id} for customer {customer_id}")
    
    def _create_system_prompt(self, language: str = "en") -> str:
        """
        Create system prompt with language awareness
        
        Args:
            language: ISO 639-1 language code (en, es, fr, de, etc.)
        """
        prompts = {
            "en": """You are Kineo, a warm customer support agent for e-commerce returns.

Listen to customer complaints, assess damage type (wrong_item, broken, quality_issue, etc.) 
and frustration level (0-10), then offer a personalized win-back deal.

Be empathetic, concise, and solution-oriented. Use the customer's first name.
Always respond in English.""",
            
            "es": """Eres Kineo, un agente cálido de atención al cliente para devoluciones de e-commerce.

Escucha las quejas de los clientes, evalúa el tipo de daño (wrong_item, broken, quality_issue, etc.)
y el nivel de frustración (0-10), luego ofrece un trato personalizado para recuperar al cliente.

Sé empático, conciso y orientado a soluciones. Usa el nombre del cliente.
Siempre responde en español.""",
            
            "fr": """Vous êtes Kineo, un agent chaleureux du service client pour les retours e-commerce.

Écoutez les plaintes des clients, évaluez le type de dommage (wrong_item, broken, quality_issue, etc.)
et le niveau de frustration (0-10), puis proposez une offre personnalisée pour reconquérir le client.

Soyez empathique, concis et orienté solution. Utilisez le prénom du client.
Répondez toujours en français.""",
            
            "de": """Sie sind Kineo, ein freundlicher Kundenservice-Agent für E-Commerce-Rücksendungen.

Hören Sie Kundenbeschwerden zu, bewerten Sie die Schadensart (wrong_item, broken, quality_issue, etc.)
und das Frustrationsniveau (0-10), und bieten Sie dann ein personalisiertes Rückgewinnungsangebot an.

Seien Sie einfühlsam, prägnant und lösungsorientiert. Verwenden Sie den Vornamen des Kunden.
Antworten Sie immer auf Deutsch.""",
            
            "pt": """Você é Kineo, um agente caloroso de suporte ao cliente para devoluções de e-commerce.

Ouça as reclamações dos clientes, avalie o tipo de dano (wrong_item, broken, quality_issue, etc.)
e o nível de frustração (0-10), depois ofereça um acordo personalizado para reconquistar o cliente.

Seja empático, conciso e orientado para soluções. Use o primeiro nome do cliente.
Sempre responda em português.""",
            
            "it": """Sei Kineo, un agente caloroso di assistenza clienti per i resi e-commerce.

Ascolta i reclami dei clienti, valuta il tipo di danno (wrong_item, broken, quality_issue, etc.)
e il livello di frustrazione (0-10), poi offri un accordo personalizzato per riconquistare il cliente.

Sii empatico, conciso e orientato alle soluzioni. Usa il nome del cliente.
Rispondi sempre in italiano.""",
            
            "zh": """你是Kineo，一位热情的电商退货客服代理。

倾听客户投诉，评估损坏类型（wrong_item, broken, quality_issue等）
和frustration级别（0-10），然后提供个性化的挽回优惠。

要有同理心，简洁且注重解决方案。使用客户的名字。
始终用中文回复。"""
        }
        
        return prompts.get(language, prompts["en"])
    
    def _detect_language(self, text: str) -> str:
        """
        Detect language from user input.
        Uses simple keyword matching for common languages.
        
        Args:
            text: User input text
            
        Returns:
            ISO 639-1 language code
        """
        text_lower = text.lower()
        
        # Spanish indicators
        spanish_keywords = ['hola', 'gracias', 'por favor', 'ayuda', 'problema', 'producto', 
                           'roto', 'dañado', 'equivocado', 'devolver', 'reembolso']
        if any(word in text_lower for word in spanish_keywords):
            print(f"🌍 Detected language: Spanish (es)")
            return "es"
        
        # French indicators
        french_keywords = ['bonjour', 'merci', 'sil vous plait', 'aide', 'problème', 
                          'produit', 'cassé', 'endommagé', 'mauvais', 'retour', 'remboursement']
        if any(word in text_lower for word in french_keywords):
            print(f"🌍 Detected language: French (fr)")
            return "fr"
        
        # German indicators
        german_keywords = ['hallo', 'danke', 'bitte', 'hilfe', 'problem', 'produkt',
                          'kaputt', 'beschädigt', 'falsch', 'rücksendung', 'erstattung']
        if any(word in text_lower for word in german_keywords):
            print(f"🌍 Detected language: German (de)")
            return "de"
        
        # Portuguese indicators
        portuguese_keywords = ['olá', 'obrigado', 'obrigada', 'por favor', 'ajuda', 
                              'problema', 'produto', 'quebrado', 'danificado', 'errado', 'devolução']
        if any(word in text_lower for word in portuguese_keywords):
            print(f"🌍 Detected language: Portuguese (pt)")
            return "pt"
        
        # Italian indicators
        italian_keywords = ['ciao', 'grazie', 'per favore', 'aiuto', 'problema',
                           'prodotto', 'rotto', 'danneggiato', 'sbagliato', 'reso', 'rimborso']
        if any(word in text_lower for word in italian_keywords):
            print(f"🌍 Detected language: Italian (it)")
            return "it"
        
        # Chinese indicators (simplified)
        chinese_keywords = ['你好', '谢谢', '请', '帮助', '问题', '产品', '坏了', '损坏', '错误', '退货', '退款']
        if any(word in text for word in chinese_keywords):
            print(f"🌍 Detected language: Chinese (zh)")
            return "zh"
        
        # Default to English
        print(f"🌍 Detected language: English (en) [default]")
        return "en"
    
    async def start(self):
        """Start the session"""
        try:
            print(f"\n🔄 Starting Gemini audio session for {self.customer_id}...")
            
            # Get customer data
            self.customer_data = get_customer(self.customer_id)
            self.is_active = True
            
            print(f"✅ Session started")
            print(f"   Customer: {self.customer_data['name']}")
            
            # Keep session alive
            while self.is_active:
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print(f"❌ Error starting session: {e}")
            raise
    
    async def send_audio(self, audio_data: str):
        """Buffer audio data (disabled - no speech-to-text available)"""
        if not self.is_active:
            return
        
        # Just buffer audio, don't process automatically
        # In production, you'd use Google Speech-to-Text API here
        self.audio_buffer.append(audio_data)
    
    async def send_video(self, video_frame: str):
        """Process video frame (optional, for context)"""
        # Store latest frame for context
        self.latest_video_frame = video_frame
    
    async def send_text(self, text: str):
        """Send text message with language detection"""
        if not self.is_active:
            print(f"⚠️ Session not active, ignoring text: {text}")
            return
        
        try:
            print(f"\n📨 Received user text: {text}")
            
            # Detect language on first message
            if not self.language_detected:
                self.detected_language = self._detect_language(text)
                self.system_prompt = self._create_system_prompt(self.detected_language)
                self.language_detected = True
                print(f"✅ Language set to: {self.detected_language}")
            
            # Generate response
            response_text = await self._generate_response(text)
            print(f"🤖 Generated response: {response_text}")
            
            # Send text back
            if self.on_text_response:
                await self.on_text_response(response_text)
                print(f"✅ Sent response via callback")
            else:
                print(f"⚠️ No on_text_response callback set!")
            
            # Check if we should score churn
            if any(keyword in text.lower() for keyword in ['wrong', 'broken', 'defective', 'damaged', 'unhappy', 'frustrated']):
                print(f"🎯 Triggering churn scoring...")
                await self._trigger_churn_scoring(text, response_text)
                
        except Exception as e:
            print(f"❌ Error sending text: {e}")
            import traceback
            traceback.print_exc()
    
    async def _process_audio_buffer(self):
        """Process buffered audio and generate response"""
        if not self.audio_buffer:
            return
        
        try:
            # For now, simulate audio processing by converting to text
            # In production, you'd use speech-to-text
            text = "[Audio captured - simulated transcription]"
            
            # Generate response using text
            response_text = await self._generate_response(text)
            
            # Send response
            if self.on_text_response:
                await self.on_text_response(response_text)
            
            # Generate audio response (text-to-speech)
            # For now, just send text - browser can use Web Speech API
            if self.on_audio_response:
                # Simulate audio by sending text that browser will speak
                await self.on_audio_response(f"TEXT_TO_SPEAK:{response_text}")
            
            # Clear buffer
            self.audio_buffer = []
            
        except Exception as e:
            print(f"❌ Error processing audio: {e}")
    
    async def _generate_response(self, user_input: str) -> str:
        """Generate response using Gemini"""
        try:
            # Build conversation context
            customer_info = json.dumps(self.customer_data, indent=2)
            prompt = f"""{self.system_prompt}

CUSTOMER PROFILE:
{customer_info}

CONVERSATION:
User: {user_input}

Respond naturally and empathetically (1-2 sentences):"""
            
            print(f"🔄 Calling Gemini API with model: {self.model_id}")
            
            # Generate with Gemini
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt
            )
            
            response_text = response.text
            print(f"✅ Gemini API returned: {response_text}")
            
            # Add to history
            self.conversation_history.append({"role": "user", "content": user_input})
            self.conversation_history.append({"role": "agent", "content": response_text})
            
            return response_text
            
        except Exception as e:
            print(f"❌ Error generating response: {e}")
            
            # Check if it's a quota error
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower():
                print("⚠️ API quota exceeded - using demo mode fallback")
                # Generate contextual demo response
                return self._generate_demo_response(user_input)
            
            import traceback
            traceback.print_exc()
            return "I apologize, I'm having trouble processing that. Could you please repeat?"
    
    async def _trigger_churn_scoring(self, user_input: str, agent_response: str):
        """Trigger churn scoring based on conversation"""
        try:
            # Analyze the conversation to determine damage type and frustration
            damage_label = self._detect_damage_type(user_input)
            frustration_score = self._detect_frustration(user_input)
            
            # Score churn
            result = score_churn(
                customer=self.customer_data,
                damage_label=damage_label,
                frustration_score=frustration_score
            )
            
            print(f"🎯 Churn Score: {result['score']} ({result['tier']})")
            
            # Save to Firestore
            save_session_log(
                session_id=self.session_id,
                customer_id=self.customer_id,
                transcript=[{
                    "user": user_input,
                    "agent": agent_response
                }],
                churn_score=result['score'],
                offer_text=result['offer']
            )
            
            # Send offer
            if self.on_text_response:
                await self.on_text_response(f"\n💡 {result['offer']}")
            
            if self.on_tool_call:
                await self.on_tool_call({
                    "tool": "score_and_respond",
                    "result": result
                })
                
        except Exception as e:
            print(f"❌ Error in churn scoring: {e}")
    
    def _detect_damage_type(self, text: str) -> str:
        """Detect damage type from text"""
        text_lower = text.lower()
        
        if 'wrong' in text_lower or 'incorrect' in text_lower:
            return 'wrong_item'
        elif 'broken' in text_lower or 'shattered' in text_lower:
            return 'broken'
        elif 'defective' in text_lower or 'not working' in text_lower:
            return 'defective'
        elif 'damaged' in text_lower:
            return 'damaged'
        elif 'quality' in text_lower or 'cheap' in text_lower:
            return 'quality_issue'
        else:
            return 'not_as_described'
    
    def _detect_frustration(self, text: str) -> float:
        """Detect frustration level from text"""
        text_lower = text.lower()
        
        frustration_keywords = {
            'very frustrated': 9.0,
            'extremely upset': 9.0,
            'angry': 8.0,
            'frustrated': 7.0,
            'disappointed': 5.0,
            'unhappy': 5.0,
            'annoyed': 6.0
        }
        
        for keyword, score in frustration_keywords.items():
            if keyword in text_lower:
                return score
        
        return 4.0  # Default moderate frustration
    
    def _generate_demo_response(self, user_input: str) -> str:
        """Generate contextual demo response when API is unavailable (multi-language support)"""
        first_name = self.customer_data.get('name', 'valued customer').split()[0]
        loyalty = self.customer_data.get('loyalty_tier', 'bronze').title()
        lang = self.detected_language
        
        # Detect issue type
        text_lower = user_input.lower()
        
        # Multi-language response templates
        responses = {
            "en": {
                "wrong": f"I'm so sorry {first_name}, that's incredibly frustrating. Let me help you resolve this shipping error right away.",
                "broken": f"{first_name}, I deeply apologize for the damaged product. As our {loyalty} member, we'll make this right immediately.",
                "quality": f"I understand your disappointment, {first_name}. This doesn't meet our standards, and we value your feedback greatly.",
                "defective": f"{first_name}, I'm truly sorry the product isn't working properly. Let's get you a replacement right away.",
                "late": f"I sincerely apologize for the delivery delay, {first_name}. That's not the experience we want for you.",
                "greeting": f"Hello {first_name}! I'm Kineo, and I'm here to help with your return. What happened with your order?",
                "default": f"Thank you for sharing that, {first_name}. I'm here to help resolve this for you quickly."
            },
            "es": {
                "wrong": f"Lo siento mucho {first_name}, eso es increíblemente frustrante. Déjame ayudarte a resolver este error de envío de inmediato.",
                "broken": f"{first_name}, me disculpo profundamente por el producto dañado. Como nuestro miembro {loyalty}, haremos esto bien de inmediato.",
                "quality": f"Entiendo tu decepción, {first_name}. Esto no cumple con nuestros estándares, y valoramos mucho tus comentarios.",
                "defective": f"{first_name}, lamento mucho que el producto no funcione correctamente. Consigamos un reemplazo de inmediato.",
                "late": f"Me disculpo sinceramente por el retraso en la entrega, {first_name}. Esa no es la experiencia que queremos para ti.",
                "greeting": f"¡Hola {first_name}! Soy Kineo, y estoy aquí para ayudarte con tu devolución. ¿Qué pasó con tu pedido?",
                "default": f"Gracias por compartir eso, {first_name}. Estoy aquí para ayudarte a resolver esto rápidamente."
            },
            "fr": {
                "wrong": f"Je suis vraiment désolé {first_name}, c'est incroyablement frustrant. Laissez-moi vous aider à résoudre cette erreur d'expédition immédiatement.",
                "broken": f"{first_name}, je m'excuse profondément pour le produit endommagé. En tant que membre {loyalty}, nous allons arranger cela immédiatement.",
                "quality": f"Je comprends votre déception, {first_name}. Cela ne répond pas à nos standards, et nous apprécions beaucoup vos commentaires.",
                "defective": f"{first_name}, je suis vraiment désolé que le produit ne fonctionne pas correctement. Obtenons un remplacement immédiatement.",
                "late": f"Je m'excuse sincèrement pour le retard de livraison, {first_name}. Ce n'est pas l'expérience que nous voulons pour vous.",
                "greeting": f"Bonjour {first_name}! Je suis Kineo, et je suis là pour vous aider avec votre retour. Que s'est-il passé avec votre commande?",
                "default": f"Merci de partager cela, {first_name}. Je suis là pour vous aider à résoudre cela rapidement."
            },
            "de": {
                "wrong": f"Es tut mir so leid {first_name}, das ist unglaublich frustrierend. Lassen Sie mich Ihnen helfen, diesen Versandfehler sofort zu beheben.",
                "broken": f"{first_name}, ich entschuldige mich zutiefst für das beschädigte Produkt. Als unser {loyalty}-Mitglied werden wir dies sofort richtig stellen.",
                "quality": f"Ich verstehe Ihre Enttäuschung, {first_name}. Dies entspricht nicht unseren Standards, und wir schätzen Ihr Feedback sehr.",
                "defective": f"{first_name}, es tut mir wirklich leid, dass das Produkt nicht richtig funktioniert. Lassen Sie uns sofort einen Ersatz erhalten.",
                "late": f"Ich entschuldige mich aufrichtig für die Lieferverzögerung, {first_name}. Das ist nicht die Erfahrung, die wir für Sie wollen.",
                "greeting": f"Hallo {first_name}! Ich bin Kineo und bin hier, um Ihnen bei Ihrer Rückgabe zu helfen. Was ist mit Ihrer Bestellung passiert?",
                "default": f"Danke, dass Sie das mitgeteilt haben, {first_name}. Ich bin hier, um Ihnen zu helfen, dies schnell zu lösen."
            },
            "pt": {
                "wrong": f"Sinto muito {first_name}, isso é incrivelmente frustrante. Deixe-me ajudá-lo a resolver este erro de envio imediatamente.",
                "broken": f"{first_name}, peço desculpas profundamente pelo produto danificado. Como nosso membro {loyalty}, vamos resolver isso imediatamente.",
                "quality": f"Entendo sua decepção, {first_name}. Isso não atende aos nossos padrões, e valorizamos muito seu feedback.",
                "defective": f"{first_name}, sinto muito que o produto não esteja funcionando corretamente. Vamos conseguir uma substituição imediatamente.",
                "late": f"Peço desculpas sinceramente pelo atraso na entrega, {first_name}. Essa não é a experiência que queremos para você.",
                "greeting": f"Olá {first_name}! Sou Kineo, e estou aqui para ajudar com sua devolução. O que aconteceu com seu pedido?",
                "default": f"Obrigado por compartilhar isso, {first_name}. Estou aqui para ajudá-lo a resolver isso rapidamente."
            }
        }
        
        # Get language-specific responses (default to English)
        lang_responses = responses.get(lang, responses["en"])
        
        # Determine response type based on user input
        if 'wrong' in text_lower or 'incorrect' in text_lower or 'missing' in text_lower or 'equivocado' in text_lower or 'mauvais' in text_lower or 'falsch' in text_lower or 'errado' in text_lower:
            return lang_responses["wrong"]
        elif 'broken' in text_lower or 'damaged' in text_lower or 'shattered' in text_lower or 'roto' in text_lower or 'dañado' in text_lower or 'cassé' in text_lower or 'kaputt' in text_lower or 'quebrado' in text_lower:
            return lang_responses["broken"]
        elif 'quality' in text_lower or 'disappointed' in text_lower or 'poor' in text_lower or 'calidad' in text_lower or 'qualité' in text_lower or 'qualität' in text_lower or 'qualidade' in text_lower:
            return lang_responses["quality"]
        elif 'defective' in text_lower or 'not working' in text_lower or 'defectuoso' in text_lower or 'défectueux' in text_lower or 'defekt' in text_lower or 'defeituoso' in text_lower:
            return lang_responses["defective"]
        elif 'late' in text_lower or 'delayed' in text_lower or 'slow' in text_lower or 'tarde' in text_lower or 'retard' in text_lower or 'verspätet' in text_lower or 'atrasado' in text_lower:
            return lang_responses["late"]
        elif any(greeting in text_lower for greeting in ['hello', 'hi', 'hey', 'hola', 'bonjour', 'hallo', 'olá']):
            return lang_responses["greeting"]
        else:
            return lang_responses["default"]
    
    async def stop(self):
        """Stop the session"""
        self.is_active = False
        print(f"🛑 Session stopped: {self.session_id}")
